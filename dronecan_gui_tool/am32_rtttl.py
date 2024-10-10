#
# Copyright (C) 2024 DroneCAN Development Team <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Huibean Luo <huibean.luo@vimdrones.com>
#
import re
import math
import dronecan

class AM32_Rtttl:
    @staticmethod
    def parse(rtttl):
        REQUIRED_SECTIONS_NUM = 3
        SECTIONS = rtttl.split(':')

        if len(SECTIONS) != REQUIRED_SECTIONS_NUM:
            raise ValueError('Invalid RTTTL string.')

        NAME = AM32_Rtttl.get_name(SECTIONS[0])
        DEFAULTS = AM32_Rtttl.get_defaults(SECTIONS[1])
        MELODY = AM32_Rtttl.get_data(SECTIONS[2], DEFAULTS)

        return {
            'name': NAME,
            'defaults': DEFAULTS,
            'melody': MELODY
        }

    @staticmethod
    def to_am32_startup_melody(rtttl, startup_melody_length=128):
        if rtttl == '':
            return {
                'data': bytearray(128),
                'errorCodes': None 
            }
        parsed_data = AM32_Rtttl.parse(rtttl)

        if startup_melody_length < 4:
            raise ValueError('startupMelodyLength is too small to fit a am32 Startup Melody')

        MAX_ITEM_VALUE = 2**8
        melody = parsed_data['melody']
        result = bytearray(startup_melody_length)
        error_codes = [0] * len(melody)

        bpm = int(parsed_data['defaults']['bpm']) % (2**16)
        result[0] = (bpm >> 8) & (2**8 - 1)
        result[1] = bpm & (2**8 - 1)
        result[2] = int(parsed_data['defaults']['octave']) % MAX_ITEM_VALUE
        result[3] = int(parsed_data['defaults']['duration']) % MAX_ITEM_VALUE

        current_result_index = 4
        current_melody_index = 0

        while current_melody_index < len(melody) and current_result_index < len(result):
            item = melody[current_melody_index]

            if item['frequency'] != 0:
                temp3 = AM32_Rtttl._calculate_am32_temp3_from_frequency(item['frequency'])

                if 0 < temp3 < MAX_ITEM_VALUE:
                    duration_per_pulse_ms = 1000 / item['frequency']
                    pulses_needed = round(item['duration'] / duration_per_pulse_ms)

                    while pulses_needed > 0 and current_result_index < len(result):
                        result[current_result_index] = min(pulses_needed, MAX_ITEM_VALUE - 1)
                        result[current_result_index + 1] = temp3
                        current_result_index += 2
                        pulses_needed -= result[current_result_index - 2]

                    if pulses_needed > 0:
                        error_codes[current_melody_index] = 2
                    else:
                        error_codes[current_melody_index] = 0
                else:
                    error_codes[current_melody_index] = 1
            else:
                duration = round(item['duration'])

                while duration > 0 and current_result_index < len(result):
                    result[current_result_index] = min(duration, MAX_ITEM_VALUE - 1)
                    result[current_result_index + 1] = 0
                    current_result_index += 2
                    duration -= result[current_result_index - 2]

                if duration > 0:
                    error_codes[current_melody_index] = 2
                else:
                    error_codes[current_melody_index] = 0

            current_melody_index += 1

        while current_melody_index < len(melody):
            error_codes[current_melody_index] = 2
            current_melody_index += 1

        return {
            'data': result,
            'errorCodes': error_codes
        }

    @staticmethod
    def is_am32_melody_param(param_struct):
        return param_struct.name == "STARTUP_TUNE" and dronecan.get_active_union_field(param_struct.value) == 'string_value'

    @staticmethod
    def is_am32_melody_param_from_file(name):
        return name == "STARTUP_TUNE"

    @staticmethod
    def from_am32_startup_melody(startup_melody_data, melody_name='Melody'):
        if isinstance(startup_melody_data, bytearray) and all(byte == 0 for byte in startup_melody_data):
            return ''

        if len(startup_melody_data) < 4:
            return f'{melody_name}:d=1,o=4,bpm=100:'

        defaults = {
            'bpm': (startup_melody_data[0] << 8) + startup_melody_data[1],
            'octave': startup_melody_data[2],
            'duration': startup_melody_data[3]
        }

        melody_notes = []
        for i in range(4, len(startup_melody_data) - 1, 2):
            freq = AM32_Rtttl._calculate_frequency_from_am32_temp3(startup_melody_data[i + 1])
            note = AM32_Rtttl._calculate_note_name_from_frequency(freq)
            octave = AM32_Rtttl._calculate_note_octave_from_frequency(freq)
            dur = startup_melody_data[i] if freq == 0 else (1000 / AM32_Rtttl._calculate_frequency(note, octave)) * startup_melody_data[i]

            if dur > 0:
                if melody_notes and abs(melody_notes[-1]['frequency'] - freq) < 0.01 and startup_melody_data[i - 2] == 255:
                    melody_notes[-1]['duration'] += dur
                else:
                    melody_notes.append({
                        'duration': dur,
                        'frequency': freq,
                        'musicalNote': note,
                        'musicalOctave': octave
                    })
            else:
                break

        full_note_duration = 4 * 60000 / defaults['bpm']
        smallest_musical_duration = full_note_duration / 64

        def quantized_duration(duration):
            return round(duration / smallest_musical_duration) * smallest_musical_duration

        melody_string = ''
        for item in melody_notes:
            musical_duration = quantized_duration(item['duration']) / full_note_duration

            while musical_duration > 1 / 64:
                current_duration = min(1.5, musical_duration)
                rtttl_duration = 2 ** -math.floor(math.log2(current_duration))
                is_dotted_note = current_duration * rtttl_duration > 1
                melody_string += ('' if rtttl_duration == defaults['duration'] else str(rtttl_duration)) + \
                                 item['musicalNote'] + \
                                 ('' if item['musicalOctave'] == defaults['octave'] or item['musicalOctave'] == 0 else str(item['musicalOctave'])) + \
                                 ('.' if is_dotted_note else '') + ','
                musical_duration -= current_duration

        return f"{melody_name}:b={defaults['bpm']},o={defaults['octave']},d={defaults['duration']}:{melody_string.rstrip(',')}"

    @staticmethod
    def get_melody_string_from_dronecan_param_value(value):
        if all(item == 255 for item in value):
            return ''
        melody_array = bytearray(128) 
        for i in range(len(value)):
            melody_array[i] = value[i]
        melody_string = AM32_Rtttl.from_am32_startup_melody(melody_array, "Melody")
        return melody_string 

    @staticmethod
    def get_name(name):
        MAX_LENGTH = 10

        if len(name) > MAX_LENGTH:
            print('Warning: Tune name should not exceed 10 characters.')

        return name or 'Unknown'

    @staticmethod
    def get_defaults(defaults):
        VALUES = defaults.split(',')

        ALLOWED_DURATION = ['1', '2', '4', '8', '16', '32']
        ALLOWED_OCTAVE = ['4', '5', '6', '7']
        ALLOWED_BPM = [
            '25', '28', '31', '35', '40', '45', '50', '56', '63', '70', '80', '90', '100',
            '112', '125', '140', '160', '180', '200', '225', '250', '285', '320', '355',
            '400', '450', '500', '565', '570', '635', '715', '800', '900'
        ]

        DEFAULT_VALUES = {
            'duration': '4',
            'octave': '6',
            'bpm': '63'
        }

        for value in VALUES:
            if value:
                KEY, VAL = value.split('=')
                if KEY == 'd' and VAL in ALLOWED_DURATION:
                    DEFAULT_VALUES['duration'] = VAL
                elif KEY == 'o' and VAL in ALLOWED_OCTAVE:
                    DEFAULT_VALUES['octave'] = VAL
                elif KEY == 'b' and VAL in ALLOWED_BPM:
                    DEFAULT_VALUES['bpm'] = VAL

        return {**DEFAULT_VALUES}

    @staticmethod
    def _calculate_semitones_from_c4(note, octave):
        NOTE_ORDER = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
        MIDDLE_OCTAVE = 4
        SEMITONES_IN_OCTAVE = 12
        OCTAVE_JUMP = (int(octave) - MIDDLE_OCTAVE) * SEMITONES_IN_OCTAVE
        return NOTE_ORDER.index(note) + OCTAVE_JUMP

    @staticmethod
    def get_data(melody, defaults):
        NOTES = melody.split(',')
        BEAT_EVERY = 60000 / int(defaults['bpm'])

        def calculate_duration(beat_every, note_duration, dots):
            DURATION = (beat_every * 4) / note_duration
            return DURATION * (1.9375 if dots == 4 else 1.875 if dots == 3 else 1.75 if dots == 2 else 1.5 if dots == 1 else 1)

        def calculate_frequency(note, octave):
            if note == 'p':
                return 0
            C4 = 261.63
            TWELFTH_ROOT = 2 ** (1 / 12)
            N = AM32_Rtttl._calculate_semitones_from_c4(note, octave)
            return round(C4 * (TWELFTH_ROOT ** N) * 10) / 10

        def calculate_semitones_from_c4(note, octave):
            NOTE_ORDER = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
            MIDDLE_OCTAVE = 4
            SEMITONES_IN_OCTAVE = 12
            OCTAVE_JUMP = (octave - MIDDLE_OCTAVE) * SEMITONES_IN_OCTAVE
            return NOTE_ORDER.index(note) + OCTAVE_JUMP

        NOTE_REGEX = re.compile(r'(1|2|4|8|16|32|64)?((?:[a-g]|h|p)#?){1}(\.*)(1|2|3|4|5|6|7|8)?(\.*)')
        parsed_notes = []

        for note in NOTES:
            match = NOTE_REGEX.match(note)
            if match:
                NOTE_DURATION = match.group(1) or int(defaults['duration'])
                NOTE = 'b' if match.group(2) == 'h' else match.group(2)
                NOTE_OCTAVE = match.group(4) or int(defaults['octave'])
                NOTE_DOTS = match.group(3).count('.') if match.group(3) else match.group(5).count('.') if match.group(5) else 0

                parsed_notes.append({
                    'note': NOTE,
                    'duration': calculate_duration(BEAT_EVERY, float(NOTE_DURATION), NOTE_DOTS),
                    'frequency': calculate_frequency(NOTE, NOTE_OCTAVE)
                })

        return parsed_notes

    @staticmethod
    def _calculate_am32_temp3_from_frequency(freq):
        return 0 if freq == 0 else round(1000000 / (freq * 24.72) - 399.3 / 24.72)

    @staticmethod
    def _calculate_frequency_from_am32_temp3(temp3):
        return 0 if temp3 == 0 else 1000000 / (24.72 * temp3 + 399.3)

    @staticmethod
    def _calculate_note_name_from_frequency(freq):
        if freq == 0:
            return 'p'
        C4 = 261.63
        NOTE_ORDER = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
        SEMITONES_IN_OCTAVE = 12
        note_semitones = round(SEMITONES_IN_OCTAVE * math.log2(freq / C4))
        note_index = note_semitones % SEMITONES_IN_OCTAVE if note_semitones >= 0 else 12 + note_semitones % SEMITONES_IN_OCTAVE
        return NOTE_ORDER[note_index]

    @staticmethod
    def _calculate_frequency(note, octave):
        if note == 'p':
            return 0
        C4 = 261.63
        NOTE_ORDER = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']
        SEMITONES_IN_OCTAVE = 12
        MIDDLE_OCTAVE = 4
        note_index = NOTE_ORDER.index(note)
        octave_diff = int(octave) - MIDDLE_OCTAVE
        semitone_diff = note_index + (octave_diff * SEMITONES_IN_OCTAVE)
        return C4 * (2 ** (semitone_diff / SEMITONES_IN_OCTAVE))

    @staticmethod
    def _calculate_note_octave_from_frequency(freq):
        if freq == 0:
            return 0
        C4 = 261.63
        MIDDLE_OCTAVE = 4
        SEMITONES_IN_OCTAVE = 12
        note_semitones = round(SEMITONES_IN_OCTAVE * math.log2(freq / C4))
        return MIDDLE_OCTAVE + note_semitones // SEMITONES_IN_OCTAVE

if __name__ == '__main__':
    rtttl_string = "bluejay:b=570,o=4,d=32:4b,p,4e5,p,4b,p,4f#5,2p,4e5,2b5,8b5"

    print("Test RTTTL String:", rtttl_string)

    # Convert the RTTTL string to a am32 startup melody
    am32_melody = AM32_Rtttl.to_am32_startup_melody(rtttl_string, 128)

    # Extract the data array
    data_array = am32_melody['data']

    # Print the data array
    print("AM32 EEPROM Struct:", list(data_array))

    # Convert the data array back to a melody string
    melody_string = AM32_Rtttl.from_am32_startup_melody(data_array, "bluejay_converted")

    # Print the converted melody string
    print("Converted Melody String:", melody_string)

    print("Test Empty String")
    am32_melody = AM32_Rtttl.to_am32_startup_melody("", 128)
    data_array = am32_melody['data']
    print("Empty String to AM32 EEPROM Struct:", list(data_array))
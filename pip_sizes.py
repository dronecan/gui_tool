#!/usr/bin/env python

import os
import importlib.metadata

def calc_container(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size



dists = list(importlib.metadata.distributions())

data = {}
data2 = []
data3 = {}

for dist in dists:
    try:
        dist_name = dist.metadata.get('Name', 'unknown')
        path = os.path.join(str(dist.locate_file('')), dist_name)
        if not os.path.exists(path):
            path = os.path.join(str(dist.locate_file('')), dist_name.replace('-', '_'))
        size = calc_container(path)
        if size/1000 > 1.0:
            data[size] = f"{dist_name}: {size/1000} KB"
            data2.append(dist_name)
            data3[dist_name] = f"{dist_name}: {size/1000} KB"
    except OSError:
        '{} no longer exists'.format(dist.metadata['Name'])

sorted_dict = dict(sorted(data.items()))
sorted_dict2 = sorted(data2)

print("--------alpha-sorted-package-names-----------------")
for i in sorted_dict2:
    print(data3[i])

#exit()
print("\n--------size-sorted-package-info-----------------")
total = 0
for i in sorted_dict:
    print(i,sorted_dict[i])
    total += i
print("Total %.2f MByte" % (total * 1.0e-6))

	

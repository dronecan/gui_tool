#!/usr/bin/env python

import os
import pkg_resources

def calc_container(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size



dists = [d for d in pkg_resources.working_set]

data = {}
data2 = []
data3 = {}

for dist in dists:
    try:
        path = os.path.join(dist.location, dist.project_name)
        size = calc_container(path)
        if size/1000 > 1.0:
            #print (f"{dist}: {size/1000} KB")
            data[size] = f"{dist}: {size/1000} KB"
            a = f"{dist}"
            data2.append(a.split()[0])# first word
            data3[a.split()[0]] = f"{dist}: {size/1000} KB"
    except OSError:
        '{} no longer exists'.format(dist.project_name)

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

	

import os.path

boxes15 = []
f = open(os.path.join(os.path.dirname(__file__), 'boxes_15x15.data'), 'r')
for line in f.readlines():
    if not line:
        break
    [left, bottom, right, top] = [float(x) for x in line.split()]
    boxes15.append((left, bottom, right, top))

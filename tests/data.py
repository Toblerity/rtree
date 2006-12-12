
boxes15 = []
f = file('boxes_15x15.dat', 'r')
for line in f.readlines():
    if not line:
        break
    [left, bottom, right, top] = [float(x) for x in line.split()]
    boxes15.append((left, bottom, right, top))

boxes3 = []
f = file('boxes_3x3.dat', 'r')
for line in f.readlines():
    if not line:
        break
    [left, bottom, right, top] = [float(x) for x in line.split()]
    boxes3.append((left, bottom, right, top))
                
points = []
f = file('point_clusters.dat', 'r')
for line in f.readlines():
    if not line:
        break
    [left, bottom] = [float(x) for x in line.split()]
    points.append((left, bottom))

def draw_data(filename):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (1440, 720))
    d = ImageDraw.Draw(im)
    for box in boxes15:
        coords = [4.0*(box[0]+180), 4.0*(box[1]+90), 4.0*(box[2]+180), 4.0*(box[3]+90)]
        d.rectangle(coords, outline='red')
    for box in boxes3:
        coords = [4.0*(box[0]+180), 4.0*(box[1]+90), 4.0*(box[2]+180), 4.0*(box[3]+90)]
        d.rectangle(coords, outline='blue')

    im.save(filename)
    

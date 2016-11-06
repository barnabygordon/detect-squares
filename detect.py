import sys
import numpy as np
from skimage import exposure
from PIL import Image, ImageOps, ImageDraw
from scipy.ndimage import morphology, label
from osgeo import gdal
from shapely.geometry import Point, mapping
from fiona import collection

shpOut = 'data/squares.shp'
lng = 'Longitude'
lat = 'Latitude'

schema = { 'geometry': 'Point', 'properties': { 'SITEID': 'str' } }

def pixel2world(gt, x, y):

    gsd = gt[1]
    ulX, ulY = gt[0], gt[3]

    lng, lat = x*gsd+ulX, y*gsd+ulY

    return lng, lat

def boxes(orig):

    p2, p98 = np.percentile(orig, (2, 98))
    im = exposure.rescale_intensity(orig, in_range=(p2, p98))

    # Inner morphological gradient.
    im = morphology.grey_dilation(im, (3, 3)) - im

    # Binarize.
    mean, std = im.mean(), im.std()
    t = mean + std
    im[im < t] = 0
    im[im >= t] = 1

    # Connected components.
    lbl, numcc = label(im)
    # Size threshold.
    min_size = 20 # pixels
    box = []
    for i in range(1, numcc + 1):
        py, px = np.nonzero(lbl == i)
        if len(py) < min_size:
            im[lbl == i] = 0
            continue

        xmin, xmax, ymin, ymax = px.min(), px.max(), py.min(), py.max()
        # Four corners and centroid.
        box.append([
            [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)],
            (np.mean(px), np.mean(py))])

    return im.astype(np.uint8) * 255, box

def detect(image_file):

    src = gdal.Open(image_file)
    gt = src.GetGeoTransform()
    orig = src.ReadAsArray()
    image_type = image_file.split('.')[1]

    im, box = boxes(orig)

    # Draw perfect rectangles and the component centroid.
    img = Image.fromarray(im)
    visual = img.convert('RGB')
    draw = ImageDraw.Draw(visual)
    with collection(shpOut, "w", "ESRI Shapefile", schema) as output:
        for b, centroid in box:
            draw.line(b + [b[0]], fill='green')
            cx, cy = centroid
            lng, lat = pixel2world(gt, cx, cy)
            point = Point(lng, lat)
            output.write({
                'properties': {'SITEID': 'hello'},
                'geometry': mapping(point)
            })
            draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill='red')
        visual.save(image_file.replace('.%s'%(image_type), '_squares.png'))


detect(sys.argv[1])
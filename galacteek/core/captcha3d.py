from io import BytesIO
import numpy
import pylab
from PIL import Image, ImageDraw, ImageFont
from mpl_toolkits.mplot3d import Axes3D


def generate(text: str):
    file = BytesIO()
    sz = (120, 40)

    img = Image.new('L', sz, 255)

    drw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 24)
    drw.text((5, 3), text, font=font)

    X, Y = numpy.meshgrid(range(sz[0]), range(sz[1]))
    Z = 1 - numpy.asarray(img) / 255

    fig = pylab.figure()
    ax = Axes3D(fig, elev=35)
    ax.plot_wireframe(X, -Y, Z, rstride=1, cstride=3)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_axis_off()
    ax.set_zlim((0, 15))
    ax.set_xlim((0, 100))

    fig.savefig(file)
    file.seek(0, 0)
    return file

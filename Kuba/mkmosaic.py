import bzpost
import datetime, requests, os, glob
import numpy as np
#import matplotlib.pylab as plt
from astropy.io import fits

sourceUrl = 'http://space.astro.cz/bolidozor/OBSUPICE/OBSUPICE-R4/'

def download_file(url):
    local_filename = url.split('/')[-1]
    # note the stream=True parameter
    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    return local_filename

def download_fits(dir, year_start, month_start, day_start, hour_start, minute_start, year_end, month_end, day_end, hour_end, minute_end):
    '''
    Creates subdirectory 'snapshots' and downloads set of fits images from http://space.astro.cz/bolidozor/ from time period given in arguments. Returns list of image names.
    >>>import getboli
    >>>getboli.download_fits('snapshots',2015,8,8,4,1,2015,8,9,6,1)
    >>>
    '''
    collector = []
    wd = os.getcwd()
    if not os.path.exists(dir):
        os.makedirs(dir)
    os.chdir(dir)
    con = bzpost.HTTPConnector(sourceUrl)
    con.connect()
    
    names = []

    for snapshot in con.get_snapshots(datetime.datetime(year_start, month_start, day_start, hour_start, minute_start), datetime.datetime(year_end, month_end, day_end, hour_end, minute_end)):
       collector.append(snapshot.url) 
       names.append(snapshot.file_name)

    for url in collector:
        download_file(url)

    con.close()
    os.chdir(wd)
    return names

def mkmosaic(dir, output='out.fits', axis='y', part=1):
    '''
    Concatenate specified parts of images from directory along the geometric axis. Plots the output by default. Having something else than fits files in target directory will likely result in error.

    :dir: The directory in which fits images are situated.
    :output: The filename of the output concaternated image.
    :axis: The axis in cartesian coordinate system along which the pictures are added.
    :part: What part of the fits images should be added. Default fits images have header on 0 and image part on 1. Raw files have each channel on 0, 1, 2 without a header.
    :return: Nothing.

    >>>import getboli
    >>>getboli.mkmosaic('snapshots', 'out.fits', axis='x', part='0')
    >>>

    TODO: .*\.fits regex
    '''
    for image in os.listdir(dir):
        hdulist = fits.open(os.path.join(dir, image))
        if 'a' in locals():
            if axis == 'x':
                a = np.append(a, hdulist[part].data, axis=1)
            if axis == 'y':
                a = np.append(a, hdulist[part].data, axis=0)
            if axis == 'z':
                a = np.add(a, hdulist[part].data)
        else:
            a = hdulist[part].data #matrix representing the image part
        hdulist.close()
    hdu = fits.PrimaryHDU(a)
    hdu.writeto(output)
    del a #when axis were switched the variable caused skip of the else condition

def split_single(image):
    """Split three channels raw file converted into fits format into respective files containing one channel. Color is appended into filename.

    :image: Imput image.
    :returns: Nothing.

    """
    filename = image.split('.')[0]
    hdulist = fits.open(image)
    all_channels = hdulist[0].data
    r = all_channels[0]
    g = all_channels[1]
    b = all_channels[2]
    for i in ['r','g','b']:
        hdu = fits.PrimaryHDU(eval(i))
        hdu.writeto(filename + '_' + i + '.fits')
    
def split_dir(dir):
    """Iterate through fits images with multiple color channels and split their parts into fits with only one color channel and append that color to generated filename.

    :dir: The directory in which three channel fits are present.
    :returns: Nothing.

    """
    wd = os.getcwd()
    os.chdir(dir)
    fits_files = glob.glob('*.fits')
    for image in fits_files:
        #imagepath = os.path.join(dir, image)
        try:
            split_single(image)
        except:
            os.chdir(wd)
    os.chdir(wd)

# apparently not needed, glob.glob
def regex_dir(dir):
    """Return list of files ending with '.fits' from specified directory. """
    dir_content = os.listdir(dir)
    collector = []
    for file in dir_content:
        try:
            match = re.match('.*fits', file).group() 
            collector = collector.append(match)
        except:
            pass
    return collector
    

# Gallery 1.x to Piwigo Migration

## Introduction
This is a framework for migrating from Gallery 1.x to any photo gallery software.

I have used this to migrate around 25 albums and 13,000 photos from Gallery 1.5 to Piwigo.

Anyone interested in collaboration is welcome.

## General
There are two Python scripts:

### Collect Gallery Metadata
The `collect_gallery_meta_data.py` script takes any album located in the Gallery 1.x root as a command-line argument and then goes through all of its sub-albums and photos in each sub-album.

It collects the following data:

#### Albums
- Album name: folder name
- Album parent album, if any
- Album caption
- Album title
- Album description

This information is stored in a MySQL (or any SQLAlchemy-supported) database table `albums`.

#### Photos
- Photo filename
- Photo caption
- Photo title
- Photo description
- Photo capture date
- Photo upload date
- Photo URL on Gallery

This information is stored in a MySQL (or any SQLAlchemy-supported) database table `photos`.

#### Collected Data and Use
With the data collected, we now have a database containing metadata for all albums and photos that were stored in Gallery 1.x. We can use this data to store all the photos, captions, capture dates, and more in a database and essentially use this data to migrate to any photo gallery software or create our own photo gallery software.

### Migrate to Piwigo
Now that we have all the data, we can use the script `execute_migration.py` to perform the actual migration. It takes the source root album as a command-line argument. It then processes the contents of the album and creates the root album itself, as well as its sub-albums, in Piwigo. The photos are uploaded with the following information to Piwigo: capture date, upload date, caption, title, and description.

All photos are downloaded from Gallery 1.x, and they need to be downloaded only once. The field `downloaded` is set to 1 when the download is complete. The same applies to Piwigo uploads. Once the photo is successfully uploaded, the field `uploaded` is set to 1. The `albums` table also has a column `migrated`, which is set to 1 once an album is migrated. This ensures that if your migration is aborted in the middle of migrating an album with its sub-albums and photos, you can safely continue from where you left off.

## Usage
Both collecting metadata and migration are expected to be handle album by album. These approach has been tested only with albums on Gallery root and it handles tehir sub albums as well.

Collect metadata: ```./collect_gallery_meta_data.py [album_name]```
Execute migration: ```./execute_migration.py [album_name]```

For more detailed instructions please check my [blog post](https://www.auroranrunner.com/2024/08/04/migrating-from-gallery-menalto-1-x-to-piwigo-an-open-source-solution/)
.

## Functionality
This code has been tested by successfully migrating over 13,000 photos across 25 albums and sub-albums. It worked for me, but I take no responsibility if it does not work for you. I strongly suggest taking backups before starting anything.

The code is rather self-explanatory and can easily be modified for your own needs.

Have Fun!!!

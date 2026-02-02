# Gallery 1.x to Piwigo Migration

## Introduction
This is a framework for migrating from Gallery 1.x to any photo gallery software.

I have used this to migrate around 25 albums and 13,000 photos from Gallery 1.5 to Piwigo.

Anyone interested in collaboration is welcome.

## General
There are three Python scripts:

### 1. Collect Gallery Metadata (HTTP)
The `collect_gallery_meta_data.py` script takes any album located in the Gallery 1.x root as a command-line argument and then goes through all of its sub-albums and photos in each sub-album. It fetches data via HTTP from your Gallery installation.

### 2. Collect Gallery Metadata (File System)
The `collect_gallery_meta_data_fs.py` script is an alternative that reads directly from the local file system instead of via HTTP. Use this when you have direct access to the Gallery 1.x installation directory (e.g., mounted drive, local installation, or backed up files).

Both metadata collection scripts collect the same data:

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
- Photo URL/path on Gallery

This information is stored in a MySQL (or any SQLAlchemy-supported) database table `photos`.

#### Collected Data and Use
With the data collected, we now have a database containing metadata for all albums and photos that were stored in Gallery 1.x. We can use this data to store all the photos, captions, capture dates, and more in a database and essentially use this data to migrate to any photo gallery software or create our own photo gallery software.

### 3. Migrate to Piwigo
Now that we have all the data, we can use the script `execute_migration.py` to perform the actual migration. It takes the source root album as a command-line argument. It then processes the contents of the album and creates the root album itself, as well as its sub-albums (at any nesting depth), in Piwigo. The photos are uploaded with the following information to Piwigo: capture date, upload date, caption, title, and description.

All photos are downloaded from Gallery 1.x, and they need to be downloaded only once. The field `downloaded` is set to 1 when the download is complete. The same applies to Piwigo uploads. Once the photo is successfully uploaded, the field `uploaded` is set to 1. The `albums` table also has a column `migrated`, which is set to 1 once an album is migrated. This ensures that if your migration is aborted in the middle of migrating an album with its sub-albums and photos, you can safely continue from where you left off.

## Usage
Both collecting metadata and migration are expected to be handled album by album. This approach has been tested with albums on Gallery root level - it handles their sub-albums recursively at any depth.

```bash
# Collect metadata via HTTP
./collect_gallery_meta_data.py [album_name]

# Collect metadata via file system
./collect_gallery_meta_data_fs.py [album_name]

# Execute migration to Piwigo
./execute_migration.py [album_name]
```

## Environment Variables

### HTTP Version (collect_gallery_meta_data.py)
| Variable | Description |
|----------|-------------|
| `GALLERY_BASE_URL` | URL to your Gallery 1.x installation (e.g., `http://gallery.example.com/albums`) |
| `DATABASE_URL` | SQLAlchemy database connection string (e.g., `mysql://user:pass@host/dbname`) |

### File System Version (collect_gallery_meta_data_fs.py)
| Variable | Description |
|----------|-------------|
| `GALLERY_BASE_PATH` | Local path to the Gallery 1.x albums directory (e.g., `/var/www/gallery/albums`) |
| `DATABASE_URL` | SQLAlchemy database connection string (e.g., `mysql://user:pass@host/dbname`) |

### Migration (execute_migration.py)
| Variable | Description |
|----------|-------------|
| `GALLERY_BASE_URL` | URL to your Gallery 1.x installation |
| `PIWIGO_API_URL` | Piwigo API endpoint (e.g., `http://piwigo.example.com/ws.php`) |
| `PIWIGO_USERNAME` | Piwigo admin username |
| `PIWIGO_PASSWORD` | Piwigo admin password |
| `MIG_DB_HOST` | Migration database host |
| `MIG_DB_USER` | Migration database username |
| `MIG_DB_PASSWORD` | Migration database password |
| `MIG_DB_NAME` | Migration database name |
| `PW_DB_HOST` | Piwigo database host |
| `PW_DB_USER` | Piwigo database username |
| `PW_DB_PASSWORD` | Piwigo database password |
| `PW_DB_NAME` | Piwigo database name |

## Example Workflow

```bash
# 1. Set environment variables for HTTP collection
export GALLERY_BASE_URL="http://gallery.example.com/albums"
export DATABASE_URL="mysql://user:password@localhost/migration_db"

# 2. Collect metadata for an album
./collect_gallery_meta_data.py MyVacationPhotos

# OR use file system version if you have local access
export GALLERY_BASE_PATH="/var/www/gallery/albums"
./collect_gallery_meta_data_fs.py MyVacationPhotos

# 3. Set additional environment variables for migration
export PIWIGO_API_URL="http://piwigo.example.com/ws.php"
export PIWIGO_USERNAME="admin"
export PIWIGO_PASSWORD="secret"
export MIG_DB_HOST="localhost"
export MIG_DB_USER="user"
export MIG_DB_PASSWORD="password"
export MIG_DB_NAME="migration_db"
export PW_DB_HOST="localhost"
export PW_DB_USER="piwigo_user"
export PW_DB_PASSWORD="piwigo_password"
export PW_DB_NAME="piwigo"

# 4. Execute migration
./execute_migration.py MyVacationPhotos
```

## Issues
No known issues. The app now supports nested sub-albums at any depth level.

## Functionality
This code has been tested by successfully migrating over 17,000 photos across 20 albums and sub-albums. It worked for me, but I take no responsibility if it does not work for you. I strongly suggest taking backups before starting anything.

The code is rather self-explanatory and can easily be modified for your own needs.

For more detailed instructions please check my [blog post](https://www.auroranrunner.com/2024/08/04/migrating-from-gallery-menalto-1-x-to-piwigo-an-open-source-solution/).

Have Fun!!!

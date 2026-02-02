#!/usr/bin/env python

"""
File system version of collect_gallery_meta_data.py

This module reads Gallery 1.x data directly from the file system instead of via HTTP.
Use this when you have local access to the Gallery installation directory.

Usage: ./collect_gallery_meta_data_fs.py [root_album]

Environment variables:
  - GALLERY_BASE_PATH: Path to the Gallery 1.x albums directory (required)
  - DATABASE_URL: SQLAlchemy database URL (required)
"""

import os
import sys
import logging
import phpserialize
import re
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

# Set up logging
LOG_MSG_FORMAT = '%(asctime)s,%(msecs)03d %(levelname)s [%(filename)s:%(lineno)d] - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
logFormatter = logging.Formatter(LOG_MSG_FORMAT, LOG_DATE_FORMAT)
logging.basicConfig(level=logging.DEBUG, format=LOG_MSG_FORMAT, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger(__name__)

# Constants
GALLERY_BASE_PATH = os.getenv('GALLERY_BASE_PATH', None)
DATABASE_URL = os.getenv('DATABASE_URL', None)

if GALLERY_BASE_PATH is None or DATABASE_URL is None:
    logger.error("GALLERY_BASE_PATH and DATABASE_URL environment variables need to be set.")
    sys.exit(1)

Base = declarative_base()
try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    logger.error(f"Error creating database engine: {e}")
    sys.exit(1)

Session = sessionmaker(bind=engine)
session = Session()


class Album(Base):
    __tablename__ = 'albums'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey('albums.id'), nullable=True)
    meta = Column(Text, nullable=True)
    title = Column(String(255), nullable=True)
    caption = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    subalbums = relationship('Album', backref='parent', remote_side=[id])
    photos = relationship('Photo', backref='album')


class Photo(Base):
    __tablename__ = 'photos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    album_id = Column(Integer, ForeignKey('albums.id'))
    filename = Column(String(255), nullable=False)
    capturedate = Column(DateTime, default=datetime.utcnow)
    uploaddate = Column(DateTime, default=datetime.utcnow)
    caption = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(255), nullable=True)
    meta = Column(Text, nullable=True)


def create_tables():
    Base.metadata.create_all(engine)


def decode_chars(text):
    if text is None:
        return ''
    char_map = {
        '\\xC4': 'Ä',
        '\\xE4': 'ä',
        '\\xD6': 'Ö',
        '\\xF6': 'ö',
        '\\xC5': 'Å',
        '\\xE5': 'å',
        '\udcc4': 'Ä',
        '\udce4': 'ä',
        '\udcd6': 'Ö',
        '\udcf6': 'ö',
        '\udcc5': 'Å',
        '\udce5': 'å'
    }
    pattern = re.compile('|'.join(re.escape(key) for key in char_map.keys()))
    decoded_text = pattern.sub(lambda x: char_map[x.group()], text)
    return decoded_text


def read_file(filepath):
    """Read data from a local file."""
    logger.debug(f"Reading data from file: {filepath}")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(filepath, 'rb') as f:
        return f.read()


def object_hook(name, obj):
    return {key: value for key, value in obj.items()}


def parse_album_data(data):
    try:
        album_data = phpserialize.loads(data, decode_strings=True, object_hook=object_hook)
        logger.debug(f"Parsed album data: {album_data}")
        fields = album_data.get('fields', {})
        title = decode_chars(fields.get('title', ''))
        description = decode_chars(fields.get('description', ''))
        caption = decode_chars(fields.get('kuvausta', ''))
        return title, caption, description
    except Exception as e:
        logger.error(f"Error deserializing album data: {e}")
        return None, None, None


def parse_photos_data(data, album_path):
    """Parse photos.dat data. album_path is used to construct file paths."""
    def object_hook(name, obj):
        return {key: value for key, value in obj.items()}

    items = []
    try:
        data_dict = phpserialize.loads(data, decode_strings=True, object_hook=object_hook)
        logger.debug(f"Parsed data_dict: {data_dict}")
        for idx, item in data_dict.items():
            try:
                logger.debug(f"Processing item {idx}: {item}")
                if item['image'] is None:  # This is an album
                    album_dat_path = os.path.join(GALLERY_BASE_PATH, item['isAlbumName'], 'album.dat')
                    album_data = read_file(album_dat_path)
                    title, caption, description = parse_album_data(album_data)
                    logger.debug(f"Album data: title: {title}, caption: {caption}, description: {description}")
                    album_name = item['isAlbumName']
                    logger.debug(f"Detected sub-album with name: {album_name}, "
                                 f"caption: {caption}, title: {title}, description: {description}")
                    items.append({
                        'name': album_name,
                        'is_album': True,
                        'caption': caption,
                        'title': title,
                        'description': description
                    })
                else:  # This is a photo
                    caption_raw = item.get('caption', '')
                    description_raw = item['extraFields'].get('Description', '') if 'extraFields' in item else ''
                    caption = decode_chars(caption_raw)
                    description = decode_chars(description_raw)
                    raw_uploaddate = item.get('uploadDate', 0)
                    uploaddate = datetime.utcfromtimestamp(raw_uploaddate).strftime('%Y-%m-%d %H:%M:%S')
                    raw_capturedate = item.get('itemCaptureDate', datetime.utcnow())
                    capturedt = datetime(
                        int(raw_capturedate['year']),
                        int(raw_capturedate['mon']),
                        int(raw_capturedate['mday']),
                        int(raw_capturedate['hours']),
                        int(raw_capturedate['minutes']),
                        int(raw_capturedate['seconds'])
                    )
                    capturedate = capturedt.strftime('%Y-%m-%d %H:%M:%S')
                    # Store local file path instead of URL
                    filename = item['image']['name'] + '.' + item['image']['type']
                    filepath = os.path.join(album_path, filename)
                    logger.debug(f"itemCaptureDate: {capturedate}, uploadDate: {uploaddate}")
                    logger.debug(f"Raw caption: {caption_raw}, Raw description: {description_raw}")
                    logger.debug(f"Decoded caption: {caption}, Decoded description: {description}")
                    items.append({
                        'name': filename,
                        'is_album': False,
                        'capturedate': capturedate,
                        'uploaddate': uploaddate,
                        'caption': caption,
                        'description': description,
                        'url': filepath  # Using local path instead of URL
                    })
                    logger.debug(f"capturedate: {capturedate} uploaddate: {uploaddate} "
                                 f"caption: {caption} description: {description} filepath: {filepath}")
            except Exception as e:
                logger.error(f"Error processing item: {item}")
                logger.error(f"Exception: {e}")
    except ValueError as e:
        logger.error(f"Error deserializing data: {e}")
        logger.error(f"Data: {data[:1000]}...")  # Log the first 1000 characters for debugging

    return items


def insert_album(name, parent_id, meta, title, caption, description):
    album = Album(name=name, parent_id=parent_id, meta=meta, title=title, caption=caption, description=description)
    session.add(album)
    try:
        session.commit()
        logger.info(f"Inserted album: {name} with parent_id: {parent_id}")
        return album.id
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting album: {e}")


def insert_photo(album_id, filename, caption, description, url, meta, capturedate, uploaddate):
    caption = caption.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    description = description.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    photo = Photo(
        album_id=album_id,
        filename=filename,
        caption=caption,
        description=description,
        url=url,
        meta=meta,
        capturedate=capturedate,
        uploaddate=uploaddate
    )
    session.add(photo)
    try:
        session.commit()
        logger.info(f"Inserted photo: {filename} in album_id: {album_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting photo: {e}")


def process_subalbum(album_name, parent_id):
    """Recursively process sub-albums at any depth."""
    album_path = os.path.join(GALLERY_BASE_PATH, album_name)
    photos_path = os.path.join(album_path, 'photos.dat')
    try:
        photos_data = read_file(photos_path)
        photos = parse_photos_data(photos_data, album_path)
        for photo in photos:
            if photo['is_album']:
                # Recursively process nested sub-albums
                sub_album_name = photo['name']
                title = photo['title']
                caption = photo['caption']
                description = photo['description']
                sub_album_id = insert_album(sub_album_name, parent_id, sub_album_name, title, caption, description)
                process_subalbum(sub_album_name, sub_album_id)
            else:
                insert_photo(
                    parent_id,
                    photo['name'],
                    photo['caption'],
                    photo['description'],
                    photo['url'],
                    str(photo),
                    photo['capturedate'],
                    photo['uploaddate']
                )
    except FileNotFoundError as e:
        logger.warning(f"No photos.dat found for album {album_name}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing album {album_name}: {e}")


def process_root_album(root_album):
    root_album_path = os.path.join(GALLERY_BASE_PATH, str(root_album))
    root_album_photos_path = os.path.join(root_album_path, 'photos.dat')
    root_album_dat_path = os.path.join(root_album_path, 'album.dat')
    
    try:
        root_album_data = read_file(root_album_dat_path)
        title, caption, description = parse_album_data(root_album_data)
        root_album_id = insert_album(
            str(root_album),
            None,
            str(root_album),
            title=title,
            caption=caption,
            description=description
        )
        root_album_photos_data = read_file(root_album_photos_path)
        root_album_photos = parse_photos_data(root_album_photos_data, root_album_path)

        for photo in root_album_photos:
            if photo['is_album']:
                sub_album_name = photo['name']
                title = photo['title']
                caption = photo['caption']
                description = photo['description']
                sub_album_id = insert_album(sub_album_name, root_album_id, sub_album_name, title, caption, description)
                process_subalbum(sub_album_name, sub_album_id)
            else:
                insert_photo(
                    root_album_id,
                    photo['name'],
                    photo['caption'],
                    photo['description'],
                    photo['url'],
                    str(photo),
                    photo['capturedate'],
                    photo['uploaddate']
                )
    except FileNotFoundError as e:
        logger.warning(f"No photos.dat found for root_album {root_album}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing root_album {root_album}: {e}")


def main():
    create_tables()

    if len(sys.argv) < 2:
        logger.error("[root_album] not provided. Usage: ./collect_gallery_meta_data_fs.py [root_album]")
        sys.exit(1)

    root_album = sys.argv[1]
    process_root_album(root_album)
    session.close()


if __name__ == "__main__":
    main()

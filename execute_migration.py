#!/usr/bin/env python

import os, sys
import requests
import logging
import mysql.connector
from urllib.parse import quote
from xml.etree import ElementTree
import re

# Constants
GALLERY_BASE_URL =  os.getenv('GALLERY_BASE_URL', None)
PIWIGO_API_URL = os.getenv('PIWIGO_API_URL', None) # 'http://[piwigo_host]/piwigo/ws.php'
PIWIGO_USERNAME = os.getenv('PIWIGO_USERNAME', None)
PIWIGO_PASSWORD = os.getenv('PIWIGO_PASSWORD', None)
DOWNLOAD_DIR = "migration"

DB_CONFIG = {
    'host': os.getenv('MIG_DB_HOST', None),
    'user': os.getenv('MIG_DB_USER', None),
    'password': os.getenv('MIG_DB_PASSWORD', None),
    'database': os.getenv('MIG_DB_NAME', None)
}

PW_DB_CONFIG = {
    'host': os.getenv('PW_DB_HOST', None),
    'user': os.getenv('PW_DB_USER', None),
    'password': os.getenv('PW_DB_PASSWORD', None),
    'database': os.getenv('PW_DB_NAME', None)
}


# Set up logging
LOG_MSG_FORMAT = ('%(asctime)s,%(msecs)03d %(levelname)s [%(filename)s:%(lineno)d] - %(message)s')
LOG_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
logFormatter = logging.Formatter(LOG_MSG_FORMAT, LOG_DATE_FORMAT)
logging.basicConfig(level=logging.DEBUG, format=LOG_MSG_FORMAT, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger(__name__)

session = requests.Session()

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

def fetch_data(url):
    logger.debug(f"Fetching data from URL: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return response.content  # Return raw bytes

def piwigo_login():
    data = {
        'method': 'pwg.session.login',
        'username': PIWIGO_USERNAME,
        'password': PIWIGO_PASSWORD,
    }
    response = session.post(PIWIGO_API_URL, data=data)
    logger.debug(f"Login response status code: {response.status_code}")
    logger.debug(f"Login response text: {response.text}")
    result = ElementTree.fromstring(response.content)
    if result.get('stat') == 'ok':
        logger.debug("Logged in to Piwigo")
    else:
        raise Exception("Failed to log in to Piwigo")

def piwigo_create_album(name, parent_id, title, description):
    data = {
        'method': 'pwg.categories.add',
        'name': title,
        'parent': parent_id,
        'comment': description,
    }
    response = session.post(PIWIGO_API_URL, data=data)
    logger.debug(f"Create album response status code: {response.status_code}")
    logger.debug(f"Create album response text: {response.text}")
    result = ElementTree.fromstring(response.content)
    if result.get('stat') == 'ok':
        album_id = result.find('id').text
        logger.debug(f"Created album {title} with ID {album_id}")
        return album_id
    else:
        raise Exception(f"Failed to create album {title}")

def download_image(url, filepath):
    logger.debug(f"Downloading image from URL: {url} to filepath: {filepath}")
    response = requests.get(url)
    response.raise_for_status()
    with open(filepath, 'wb') as f:
        f.write(response.content)
    logger.debug(f"Downloaded image to {filepath}")

def update_album_info(album_id, title, caption, description):
    data = {
        'method': 'pwg.categories.setInfo',
        'category_id': album_id,
        'name': title,
        'comment': f"{caption} - {description}" if caption else description
    }
    response = session.post(PIWIGO_API_URL, data=data)
    logger.debug(f"Update album info response status code: {response.status_code}")
    logger.debug(f"Update album info response text: {response.text}")
    result = ElementTree.fromstring(response.content)
    if result.get('stat') != 'ok':
        raise Exception(f"Failed to update album info for album ID {album_id}")

def process_album(album_name):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    pw_conn = mysql.connector.connect(**PW_DB_CONFIG)
    pw_cursor = pw_conn.cursor(dictionary=True)

    # Fetch album info from database
    cursor.execute("SELECT * FROM albums WHERE name=%s", (album_name,))
    album = cursor.fetchone()
    logger.debug(f"Album fetched: {album}")
    if not album:
        logger.error(f"Album {album_name} not found in database")
        return

    album_id = album['id']
    album_title = album['title']
    album_caption = album['caption']
    album_description = album['description']

    # Check if the album is already created
    if album['created']:
        logger.info(f"Album {album_name} already created, skipping album creation")
        pw_cursor.execute("SELECT id FROM piwigo_categories WHERE name=%s", (album_title,))
        result = pw_cursor.fetchone()
        if result:
            logger.debug(f"Found album {album_title} in Piwigo database with ID {result['id']}")
            piwigo_album_id = result['id']
        else:
            logger.error(f"Could not find album {album_title} in Piwigo database")
            return
        # Process sub-albums
        cursor.execute("SELECT * FROM albums WHERE parent_id=%s", (album_id,))
        subalbums = cursor.fetchall()
        logger.debug(f"Subalbums fetched: {subalbums}")
        for subalbum in subalbums:
            subalbum_id = subalbum['id']
            subalbum_name = subalbum['name']
            subalbum_title = subalbum['title']
            subalbum_caption = subalbum['caption']
            subalbum_description = subalbum['description']

            if subalbum['created']:
                logger.info(f"Album {subalbum_name} already created, skipping album creation")
                pw_cursor.execute("SELECT id FROM piwigo_categories WHERE name=%s", (subalbum_title,))
                result = pw_cursor.fetchone()
                if result:
                    logger.debug(f"Found album {subalbum_title} in Piwigo database with ID {result['id']}")
                    piwigo_subalbum_id = result['id']
                else:
                    logger.error(f"Could not find sub album {subalbum_title} in Piwigo database")
                    return
            else:
                # Process sub-albums
                piwigo_login()
                piwigo_subalbum_id = piwigo_create_album(subalbum_name, piwigo_album_id, subalbum_title, subalbum_description)
                cursor.execute("UPDATE albums SET created=TRUE WHERE id=%s", (subalbum_id,))
                conn.commit()
            process_photos(subalbum_id, subalbum_name, piwigo_subalbum_id)
    else:
        # Login to Piwigo
        piwigo_login()

        # Create album in Piwigo
        logger.debug(f"Creating album {album_title} in Piwigo")
        piwigo_album_id = piwigo_create_album(album_name, None, album_title, album_description)

        # Update album info in database
        cursor.execute("UPDATE albums SET created=TRUE WHERE id=%s", (album_id,))
        conn.commit()

        # Process sub-albums
        cursor.execute("SELECT * FROM albums WHERE parent_id=%s", (album_id,))
        subalbums = cursor.fetchall()
        logger.debug(f"Subalbums fetched: {subalbums}")
        for subalbum in subalbums:
            subalbum_id = subalbum['id']
            subalbum_name = subalbum['name']
            subalbum_title = subalbum['title']
            subalbum_caption = subalbum['caption']
            subalbum_description = subalbum['description']

            piwigo_subalbum_id = piwigo_create_album(subalbum_name, piwigo_album_id, subalbum_title, subalbum_description)

            cursor.execute("UPDATE albums SET created=TRUE WHERE id=%s", (subalbum_id,))
            conn.commit()

            process_photos(subalbum_id, subalbum_name, piwigo_subalbum_id)

        # Process photos in the main album
        process_photos(album_id, album_name, piwigo_album_id)

    cursor.close()
    conn.close()
    pw_cursor.close()
    pw_conn.close()

def process_photos(album_id, album_name, piwigo_album_id):
    logger.debug(f"Processing photos for album ID {album_id}, album name {album_name}, Piwigo album ID {piwigo_album_id}")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM photos WHERE album_id=%s", (album_id,))
    photos = cursor.fetchall()
    logger.debug(f"Photos fetched: {photos}")
    # Login to Piwigo
    piwigo_login()
    for photo in photos:
        photo_path = None
        if not photo['downloaded']:
            photo_url = f"{GALLERY_BASE_URL}/{album_name}/{photo['filename']}"
            photo_path = os.path.join(DOWNLOAD_DIR, album_name, photo['filename'])
            os.makedirs(os.path.dirname(photo_path), exist_ok=True)
            try:
                download_image(photo_url, photo_path)
                cursor.execute("UPDATE photos SET downloaded=TRUE WHERE id=%s", (photo['id'],))
                conn.commit()
            except Exception as e:
                logger.error(f"Error downloading photo {photo['filename']}: {e}")
                continue
        else:
            photo_path = os.path.join(DOWNLOAD_DIR, album_name, photo['filename'])

        logger.debug(f"Photo: {photo['caption']} uploaded status: {photo['uploaded']}")
        if not photo['uploaded']:
            logger.debug(f"Photo: {photo['caption']} not uploaded, uploading")
            logger.debug(f"Photo path: {photo_path}")
        else:
            logger.debug(f"Photo: {photo['caption']} already uploaded, \
                         skipping")
        if not photo['uploaded'] and photo_path:
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as f:
                    mime_type = 'image/jpeg' if photo_path.endswith('.jpeg') or photo_path.endswith('.jpg') else 'image/png'
                    files = {'image': (photo['filename'], f, mime_type)}
                    if photo['description'] and photo['caption']:
                        photo['description'] = photo['caption'] + ' - ' + photo['description']
                    elif photo['caption']:
                        photo['description'] = photo['caption']
                    if len(photo['caption']) > 255:
                        photo['caption'] = photo['caption'][:255]
                    data = {
                        'method': 'pwg.images.addSimple',
                        'category': piwigo_album_id,
                        'name': photo['caption'],
                        'comment': photo['description'],
					    'date_creation': photo['capturedate'].strftime('%Y-%m-%d %H:%M:%S'),  # convert to string
					    'date_available': photo['uploaddate'].strftime('%Y-%m-%d %H:%M:%S')  # convert to string
                    }
                    logger.debug(f"Uploading photo: {photo['filename']} to album ID: {piwigo_album_id}")
                    logger.debug(f"Upload data: {data}")
                    response = session.post(PIWIGO_API_URL, data=data, files=files)
                    logger.debug(f"Upload photo response status code: {response.status_code}")
                    logger.debug(f"Upload photo response text: {response.text}")
                    if response.status_code == 200:
                        result = ElementTree.fromstring(response.content)
                        if result.get('stat') == 'ok':
                            cursor.execute("UPDATE photos SET uploaded=TRUE WHERE id=%s", (photo['id'],))
                            conn.commit()
                        else:
                            logger.error(f"Failed to upload photo {photo['filename']}")
                    else:
                        logger.error(f"Failed to upload photo {photo['filename']} with status code: {response.status_code}")
            else:
                logger.error(f"Photo path does not exist: {photo_path}")

    cursor.close()
    conn.close()

def main():
    album_name = sys.argv[1]
    process_album(album_name)

if __name__ == "__main__":
    main()


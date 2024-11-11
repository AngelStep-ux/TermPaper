import requests
import json
from tqdm import tqdm
import datetime
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

TOKEN_VK = config['API_KEYS']['TOKEN_VK']
YA_DISK_TOKEN = config['API_KEYS']['YA_DISK_TOKEN']
NUM_PHOTOS = 5
DOWNLOAD_FOLDER = 'VK_photos'
RESULT_JSON = 'uploaded_photos.json'

class VKAPIClient:
    API_BASE_URL = 'https://api.vk.com/method'

    def __init__(self, token):
        self.token = token

    def get_common_params(self):
        return {
            'access_token': self.token,
            'v': '5.131'
        }

    def get_profile_photos(self, user_id):
        params = self.get_common_params()
        params.update({
            'owner_id': user_id,
            'album_id': 'profile',
            'photo_sizes': 1,
            'count': NUM_PHOTOS,
            'extended': 1
        })
        response = requests.get(f'{self.API_BASE_URL}/photos.get', params=params)
        return response.json()

class YandexDisk:
    BASE_URL = 'https://cloud-api.yandex.net/v1/disk/resources'

    def __init__(self, token):
        self.token = token

    def create_folder(self, path):
        headers = {'Authorization': f'OAuth {self.token}'}
        response = requests.put(f'{self.BASE_URL}?path={path}&overwrite=true', headers=headers)
        if response.status_code == 201:
            print(f'Папка {path} создана.')
        elif response.status_code == 409:
            print(f'Папка {path} уже существует.')
        else:
            print('Ошибка при создании папки:', response.json())

    def upload_file(self, file_url, ya_path):
        headers = {'Authorization': f'OAuth {self.token}'}
        upload_url = requests.get(f'{self.BASE_URL}/upload?path={ya_path}&overwrite=true', headers=headers).json().get('href')
        img_response = requests.get(file_url)

        if img_response.status_code == 200:
            response = requests.put(upload_url, files={'file': img_response.content})
            return response.status_code == 201
        else:
            print(f'Ошибка загрузки {ya_path}: {img_response.status_code}')
            return False

    def download_photos_to_yadisk(self, photos, folder_name):
        yandex_path = folder_name + '/'
        self.create_folder(yandex_path)
        uploaded_files_info = []
        seen_likes = {}

        for photo in tqdm(photos, desc='Загрузка фотографий'):
            max_size = max(photo['sizes'], key=lambda x: x['width'] * x['height'])
            file_url = max_size['url']
            likes_count = photo.get('likes', {}).get('count', 0)

            if likes_count not in seen_likes:
                file_name = f"{likes_count}.jpg"
            else:
                date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"{likes_count}_{date_str}.jpg"

            seen_likes[likes_count] = file_name
            print(f"Обработка фотографии: {file_name}, URL: {file_url}, Likes: {likes_count}")

            if self.upload_file(file_url, yandex_path + file_name):
                print(f'Файл {file_name} загружен на Я.Диск.')
                uploaded_files_info.append({'file_name': file_name, 'size': max_size['type']})
            else:
                print(f'Ошибка при загрузке {file_name} на Я.Диск.')

        return uploaded_files_info

def save_results_to_json(uploaded_files_info):
    with open(RESULT_JSON, 'w', encoding='utf-8') as json_file:
        json.dump(uploaded_files_info, json_file, ensure_ascii=False, indent=4)
    print(f'Информация о загруженных фотографиях сохранена в {RESULT_JSON}.')

def get_user_id(token, screen_name_or_id):
    params = {
        'access_token': token,
        'v': '5.131',
        'screen_name': screen_name_or_id
    }
    response = requests.get('https://api.vk.com/method/users.get', params=params)
    user_info = response.json()
    if 'response' in user_info:
        return user_info['response'][0]['id']
    return None

def main():
    user_input = input("Введите ID или screen_name пользователя: ")
    vk_client = VKAPIClient(TOKEN_VK)
    user_id = get_user_id(TOKEN_VK, user_input)

    if user_id is not None:
        photos_info = vk_client.get_profile_photos(user_id)
        if 'response' in photos_info and 'items' in photos_info['response']:
            photos = photos_info['response']['items']
            ya_disk = YandexDisk(YA_DISK_TOKEN)
            uploaded_files_info = ya_disk.download_photos_to_yadisk(photos, DOWNLOAD_FOLDER)
            save_results_to_json(uploaded_files_info)
        else:
            print('Не удалось получить фото. Проверьте настройки конфиденциальности или корректность токена/ID пользователя.')
    else:
        print('Не удалось получить ID пользователя. Проверьте ввод или токен.')

if __name__ == '__main__':
    main()
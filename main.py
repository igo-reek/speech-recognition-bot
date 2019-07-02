import json
import tokenTelgramWit  # include telegram Token and wit.ai ACCESS_TOKEN
import telebot
from telebot.types import Message
import requests
from time import gmtime, strftime
import subprocess
import tempfile
import os
from wit import Wit
import logging
import soundfile as sf
import re
import time

bot = telebot.TeleBot(tokenTelgramWit.Token)

USERS = set()

API_ENDPOINT = 'https://api.wit.ai/speech'
client = Wit(tokenTelgramWit.ACCESS_TOKEN)
client.logger.setLevel(logging.WARNING)
headers = {'authorization': 'Bearer ' + tokenTelgramWit.ACCESS_TOKEN,
           'Content-Type': 'audio/wav'}


def read_audio(WAVE_FILENAME):
    # function to read audio(wav) file
    with open(WAVE_FILENAME, 'rb') as f:
        audio = f.read()
    return audio


def recognition_file(result, user_id):
    with open('recognition.txt', 'a') as file:
        file.write(user_id + '    ' + result + '\n')
    file.close()


def convert_to_wav(in_filename=None, in_bytes=None, idvoice=None):
    with tempfile.TemporaryFile() as temp_out_file:
        temp_in_file = None
        if in_bytes:
            temp_in_file = tempfile.NamedTemporaryFile(delete=False)
            temp_in_file.write(in_bytes)
            in_filename = temp_in_file.name
            temp_in_file.close()
        if not in_filename:
            raise Exception('Neither input file name nor input bytes is specified.')

        # Запрос в командную строку для обращения к FFmpeg
        command = [
            r'ffmpeg\bin\ffmpeg.exe',  # путь до ffmpeg.exe
            '-i', in_filename,
            r'voice\{}.wav'.format(idvoice)
        ]

        proc = subprocess.Popen(command, stdout=temp_out_file, stderr=subprocess.DEVNULL)
        proc.wait()

        if temp_in_file:
            os.remove(in_filename)

        temp_out_file.seek(0)


def parts_recognition(id_voice, message):
    data, samplerate = sf.read(r'voice\{}.wav'.format(id_voice))
    numberFrame = (len(data) // samplerate) // 19 + 1
    lenFrame = int(len(data) / numberFrame)
    frame = [data[i * int(lenFrame):(i * int(lenFrame)) + int(lenFrame)] for i in range(0, numberFrame)]

    res = ''
    resp = []
    if numberFrame == 1:
        with open(r'voice\{}.wav'.format(id_voice), 'rb') as f:
            resp = client.speech(f, None, {'Content-Type': 'audio/wav'})
        f.close()
        res = resp.get('_text')
    else:
        for i in range(0, numberFrame):
            sf.write(r'voice\{0}_{1}.wav'.format(id_voice, i), frame[i], samplerate)
        for i in range(0, numberFrame):
            with open(r'voice\{0}_{1}.wav'.format(id_voice, i), 'rb') as f:
                restext = requests.post(API_ENDPOINT, headers=headers, data=f)
                data = json.loads(restext.content)
                restext.close()
                time.sleep(1)
                text = data.get('_text')
                restext = None
            f.close()
            if res != '':
                res = res + ' ' + text
            else:
                res = text

    result = re.sub(' ', '', res)
    if len(result) == 0:
        bot.send_message(message.from_user.id, 'Поговори со мной')
    else:
        bot.send_message(message.from_user.id, res)
    return res


@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(tokenTelgramWit.Token, file_info.file_path))
    id_voice = str(message.from_user.id) + strftime("_%Y_%m_%d_%H_%M_%S", gmtime())
    voice = file.content

    convert_to_wav(in_bytes=voice, idvoice=id_voice)
    result_text = parts_recognition(id_voice, message)
    recognition_file(result_text, id_voice)


@bot.message_handler(commands=['start', 'help'])
def command_handler(message: Message):
    bot.reply_to(message, 'Отправь мне аудиосообщение')


@bot.message_handler(content_types=['text'])
def command_voice(message: Message):
    bot.send_message(message.from_user.id, 'Отправь мне аудиосообщение')


bot.polling(timeout=5)

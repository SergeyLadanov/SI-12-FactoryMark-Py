import argparse
import struct
import subprocess
from pathlib import Path
import os
import re

def get_user_input(prompt, default=None):
    """Функция для получения ввода от пользователя с возможностью указания значения по умолчанию"""
    if default:
        user_input = input(f"{prompt} [{default}]: ")
        return user_input if user_input else default
    else:
        return input(f"{prompt}: ")


def scan_files_with_extensions(directory: str, extensions: list, recursive: bool = False) -> list:
    pattern = '**/*' if recursive else '*'
    path = Path(directory)
    
    files = []
    for item in path.glob(pattern):
        if item.is_file() and item.suffix.lower() in extensions:
            files.append(item.absolute())
            
    return files

def is_valid_firmware_name(file_name: str) -> bool:
    # Регулярное выражение для проверки формата
    # pattern = r'^SI-12-MX_v\d+\.\d+\.\d+\.hex$'
    pattern = r'^SI-12-MX.hex$'
    return bool(re.match(pattern, file_name))


# def read_last_line(filename, encoding='utf-8'):
#     with open(filename, 'rb') as f:
#         f.seek(0, 2)  # Переход в конец файла
#         filesize = f.tell()
#         if filesize == 0:
#             return ''  # Пустой файл

#         offset = -1
#         while -offset < filesize:
#             f.seek(offset, 2)
#             if f.read(1) == b'\n':  # нашли конец предыдущей строки
#                 break
#             offset -= 1

#         return f.readline().decode(encoding).rstrip('\n\r')


def read_last_line(filename, encoding='utf-8'):
    """Возвращает последнюю непустую строку файла (без завершающих \r\n).
    Работает с большими файлами — читает с конца побайтно."""
    with open(filename, 'rb') as f:
        f.seek(0, 2)
        filesize = f.tell()
        if filesize == 0:
            return ''  # пустой файл

        # pointer указывает на индекс последнего байта
        pointer = filesize - 1

        # Сначала пропустим любые завершающие \n или \r (т.е. если файл заканчивается переводом строки)
        while pointer >= 0:
            f.seek(pointer)
            ch = f.read(1)
            if ch in (b'\n', b'\r'):
                pointer -= 1
            else:
                break

        if pointer < 0:
            return ''  # файл состоит только из переводов строки

        # Теперь найдем предыдущий '\n' — это граница начала последней строки
        while pointer >= 0:
            f.seek(pointer)
            if f.read(1) == b'\n':
                # начало строки — следующий байт
                f.seek(pointer + 1)
                break
            pointer -= 1
        else:
            # не нашли '\n' => читаем с начала файла
            f.seek(0)

        raw = f.readline()
        return raw.decode(encoding, errors='replace').rstrip('\r\n')

# def is_valid_bootloader_name(file_name: str) -> bool:
#     # Регулярное выражение для проверки формата
#     pattern = r'^IPM_Bootloader_v\d+\.\d+\.\d+\.hex$'
#     return bool(re.match(pattern, file_name))



def main():
    # Создаем парсер аргументов
    parser = argparse.ArgumentParser(description='Скрипт для работы с прошивкой')
    
    # Добавляем параметры
    parser.add_argument(
        '--serial', 
        type=str, 
        help='Серийный номер (например: 35)'
    )
    
    parser.add_argument(
        '--revision', 
        type=str, 
        # default='25000000',
        help='Версия (по умолчанию: 25000000)'
    )
    
    parser.add_argument(
        '--address', 
        type=str, 
        default='0x0800E800',
        help='Адрес во flash (по умолчанию: 0x0800E800)'
    )
    
    parser.add_argument(
        '--port', 
        type=str, 
        choices=['SWD', 'USB1', 'JTAG'],
        default='SWD',
        help='Тип порта (SWD, USB1 или JTAG)'
    )
    
    # Парсим аргументы
    args = parser.parse_args()

    if os.path.isfile("Revision_Log.txt"):
        last_line = read_last_line("Revision_Log.txt")
        last_line = last_line.split(';')
        args.revision = int(last_line[0]) + 1
        args.serial = int(last_line[1]) + 1
    else:
        # Проверяем обязательные параметры и запрашиваем их при отсутствии
        if not args.revision:
            args.revision = get_user_input('Введите заводской номер (например: 25000000)', None)

        if not args.serial:
            args.serial = get_user_input('Введите серийный номер (например: 35)', None)
    

    
    # Для необязательных параметров используем значения по умолчанию
    # args.revision = get_user_input('Введите версию', args.revision)
    # args.address = get_user_input('Введите адрес во flash', args.address)
    # args.port = get_user_input('Выберите тип порта (SWD, USB1, JTAG)', args.port)
    
    # Валидация порта
    if args.port not in ['SWD', 'USB1', 'JTAG']:
        print("Ошибка: неверный тип порта")
        exit(1)
    
    # Выводим полученные параметры
    print("\nИспользованные параметры:")
    print(f"Серийный номер: {args.serial}")
    print(f"Заводской номер: {args.revision}")
    print(f"Адрес: {args.address}")
    print(f"Порт: {args.port}")

    # STM32_Programmer_CLI -c port=SWD -r 0x08000000 8 device_info.bin

    arguments = ["STM32_Programmer_CLI", "-c", f"port={args.port}", "-r", f"{args.address}", "8", "device_info.bin"]

    subprocess.run(arguments)


    # Открываем файл в режиме записи байтов
    with open('device_info.bin', 'wb') as file:
        # Упаковываем число в 4-байтовое целое (формат 'i' - signed int)
        # Другие варианты форматов:
        # 'I' - unsigned int (беззнаковое)
        # '<i' - little-endian (малый порядок байтов)
        # '>i' - big-endian (большой порядок байтов)
        packed_serial_number = struct.pack('<i', int(args.serial))
        
        # Записываем в файл
        file.write(packed_serial_number)

        packed_rev_number = struct.pack('<i', int(args.revision))

        # Записываем в файл
        file.write(packed_rev_number)

    

    arguments = ["STM32_Programmer_CLI", "-c", f"port={args.port}", "-w", "device_info.bin", f"{args.address}"]

    # target_bootloader_name = ""
    target_firmware_name = ""
    # bootloader_counter = 0
    firmware_counter = 0

    extensions = ['.hex']
    files = scan_files_with_extensions(".", extensions, recursive=False)

    for file in files:
        file_name = os.path.basename(file)
        if (is_valid_firmware_name(file_name)):
            target_firmware_name = file_name
            firmware_counter += 1
        # if (is_valid_bootloader_name(file_name)):
        #     target_bootloader_name = file_name
        #     bootloader_counter += 1

    # if bootloader_counter == 0:
    #     print("Файл загрузчика не найден, установка загрузчика будет пропущена...")
    # elif bootloader_counter == 1:
    #     print(f"Будет использован файл загрузчика {target_bootloader_name}")
    #     arguments.append("-w")
    #     arguments.append(target_bootloader_name)
    # else:
    #     print("Найдено несколько версий файлов загрузчика, нужно оставить только один, операция отменена!")
    #     print("Нажмите Enter для завершения...")
    #     input()
    #     exit(1)

    if firmware_counter == 0:
        print("Файл основной программы не найден, установка основной программы будет пропущена...")
    elif firmware_counter == 1:
        print(f"Будет использован файл основной программы {target_firmware_name}")
        arguments.append("-w")
        arguments.append(target_firmware_name)
    else:
        print("Найдено несколько версий файлов основной программы, нужно оставить только один, операция отменена!")
        print("Нажмите Enter для завершения...")
        input()
        exit(1)



    result = subprocess.run(arguments)



    if (result.returncode == 0):
        print("Установка успешно завершена")
        with open("Revision_Log.txt", "a+", encoding="utf-8") as file:
            file.write(f"{args.revision};{args.serial}\n")
        print(f"Записан серийный номер {args.serial} и заводской номер {args.revision} в файл Revision_Log.txt")
    else:
        print("Ошибка при установке")



    print("Нажмите Enter для завершения...")
    input()

if __name__ == '__main__':
    main()

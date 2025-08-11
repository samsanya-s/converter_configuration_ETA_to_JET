import xml.etree.ElementTree as ET
import uuid
import re
import os
import shutil
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
from pathlib import Path
import json
import sys
import traceback
import requests
import tempfile
import subprocess


def resource_path(relative_path):
    """ Получает абсолютный путь к ресурсу, работает в .exe и в IDE """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = Path(__file__).resolve().parent
with open(resource_path('full_config.json'), 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

GLOBAL_SET_JOURNALS = set()
GLOBAL_LIST_FORM_PROP = {}
GLOBAL_COUNT_ATTRS = []
GLOBAL_EXTENSIONS = set()
APP = None

GITHUB_USER = "samsanya-s"
GITHUB_REPO = "converter_configuration_ETA_to_JET"
JSON_FILE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/data.json"
GITHUB_TOKEN = "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"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}


def get_current_version():
    if os.path.exists("version.txt"):
        with open("version.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.0.0"

def get_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"

    r = requests.get(url, timeout=10, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=30, headers=HEADERS)
    r.raise_for_status()
    with open(dest, "wb") as f:
        shutil.copyfileobj(r.raw, f)

def update_self(download_url):
    # print("🔄 Скачиваю новую версию...")
    tmp_file = os.path.join(tempfile.gettempdir(), "new_version.exe")
    download_file(download_url, tmp_file)

    current_exe = sys.argv[0]
    backup_exe = current_exe + ".old"

    os.rename(current_exe, backup_exe)
    os.rename(tmp_file, current_exe)

    # print("✅ Обновление завершено. Перезапуск...")
    os.execv(current_exe, sys.argv)

def download_json():
    # print("📥 Скачиваю актуальный JSON...")
    r = requests.get(JSON_FILE_URL, timeout=10, headers=HEADERS)
    r.raise_for_status()
    with open("data.json", "w", encoding="utf-8") as f:
        f.write(r.text)


def has_user_dictionary_with_code(file_path: str, code: str) -> bool:
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        for user_dict in root.findall('UserDictionary'):
            if user_dict.get('code') == code:
                return True
        return False
    except (ET.ParseError, FileNotFoundError) as e:
        APP.log(f"Ошибка при чтении файла: {e}", "red")
        return False

def crutch_typename(root: ET.Element):
    for elem in root.iter():
        typename = elem.attrib.get("typeName")
        if typename is None: continue
        if 'ResourceLinkNET' in typename:
            corr_typename =  typename.replace('ResourceLinkNET', 'ResourceLink')
            elem.set("typeName", corr_typename)
        elif 'ResourceLinkDict' in typename:
            corr_typename =  typename.replace('ResourceLinkDict', 'ResourceLink')
            elem.set("typeName", corr_typename)

def stringify_attributes(elem: ET.Element):
    for key, value in elem.attrib.items():
        if not isinstance(value, str):
            elem.attrib[key] = str(value)
    for child in elem:
        stringify_attributes(child)
        # if child.tag == 'FormTab' and child.get('type') == 'CUSTOM':
        #     pass
        #     # APP.log(ET.tostring(child))
        # else:
        #     stringify_attributes(child)

def gen_uuid() -> str:
    return str(uuid.uuid4())

def to_snake_case(val_name: str) -> str:
    if val_name is None:
        return None

    # Основная функция преобразования, с учётом подряд идущих заглавных букв
    def convert(text: str) -> str:
        # Разделяет только на переходе от заглавной к строчной букве после другой заглавной
        text = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', text)
        text = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', text)
        # Приводим к нижнему регистру
        return text.lower()

    # Функция для обработки текста внутри скобок
    def repl(match):
        open_br, inner, close_br = match.groups()
        return f"{open_br}{convert(inner)}{close_br}"

    # Обработка блоков в скобках
    val_name = re.sub(r'([\{\[\(\<])([A-Za-z0-9]+)([\}\]\)\>])', repl, val_name)

    # Обработка всей строки
    val_name = convert(val_name)

    # Удаление повторяющихся символов '_'
    val_name = re.sub(r'_+', '_', val_name)

    # Удаление начального и конечного '_', если есть
    val_name = val_name.strip('_')

    return val_name

def extract_param_value(params: str, key: str) -> str:
    if params is None:
        return params
    match = re.search(rf'{key}:([^;]+)', params)
    return match.group(1) if match else None

def get_attribute_by_code(props: ET.Element, code: str):
    for elem in props.findall("AttributeMigration"):
        # APP.log(elem.find("TypeParameter").get("name"))
        if elem.find("TypeParameter").get("name") == code:
            return elem
    # APP.log('aaaaaaaaaaaaaaaaaaaa', (props.findall("AttributeMigration")))
    APP.log(f'Ошибка: не удается найти атрибут с кодом {code}', "red")
    return None

def generate_new_form_item_migration(type_name: str, item_property: dict, parameters: list):
    try:
        new_root = ET.Element(CONFIG['MAPPING_TAG_FORM'][type_name], item_property)
        for param in parameters:
            if type_name == 'RunProcess':
                rp = ET.Element('Parameter', {"key": param[0]})
                rp.text =  param[1]
                new_root.append(rp)
            else:
                ET.SubElement(new_root, 'Parameter', {"key": param[0], "value": param[1]})
        return (1, new_root)
    except Exception as ex:
        return (0, traceback.format_exc())

def generate_new_meta_attribute_migration(type_param_attrs: dict):
    try:
        new_root = ET.Element('AttributeMigration', {'type': 'ADD_ATTRIBUTE', 'uuid': gen_uuid()})
        ET.SubElement(new_root, 'TypeParameter', type_param_attrs)
        return (1, new_root)
    except Exception as ex:
        return (0, traceback.format_exc())

def get_params_transient_form_item(old_item: ET.Element, code_field: str):
    try:
        type_name = old_item.get("ViewComponentType")
        if old_item.tag == 'ButtonItem':
            if len(old_item):
                type_name = old_item[0].tag
            else:
                type_name = "Button"
        tag_props = {
            "code": code_field,
            "formItemType": CONFIG['MAPPING_TYPE_INPUT'][type_name],
            "indentLevel": extract_param_value(old_item.get("Params"), "level") or 0,
            "isEnabled": "true",
            "isService": "false",
            "name": old_item.get("Label", ""),
            "helpText":  old_item.get("HelpText", ""),
        }

        if old_item.tag == 'ButtonItem':
            tag_props['label'] = old_item.get("Label", "")
            tag_props['name'] = old_item.get("Name", "")

        params = []
        # APP.log(type_name)
        if old_item.tag == 'ButtonItem':
            if old_item.find("RunProcess") is not None:
                for process in old_item.find("RunProcess").find('Processes'):
                    params.append((process.get('ProcessUUID'), process.find('EnabledExpression').text if process.find('EnabledExpression') is not None else ""))
            elif old_item.find("RunReport"):
                for process in old_item.find("RunReport").find('Processes'):
                    rep_uuid = process.get('ReportUUID')
                    if rep_uuid in CONFIG["MAPPING_REPORT_UUID"]:
                        rep_uuid = CONFIG["MAPPING_REPORT_UUID"]["rep_uuid"]
                    else:
                        APP.log(f"Внимание: не забудьте заменить uuid ({rep_uuid}) шаблона отчёта")
                    params.append((rep_uuid, ''))
        else:
            for type_param in CONFIG['MAPPING_PARAMETRS'][type_name]:
                if type_param == 'maxRows':
                    params.append((type_param, extract_param_value(old_item.get("Params"), "maxVisibleRows") or 1))
                elif type_param == 'valueGetterCode':
                    value_getter_code = old_item.get('ValueGetterCode')
                    expression = CONFIG['MAPPING_TRANSIENT_ITEM'][value_getter_code] if value_getter_code in CONFIG['MAPPING_TRANSIENT_ITEM'] else f"return '{value_getter_code}'" 
                    params.append((type_param, expression))
                elif type_param == 'valueTemplate' and old_item.get('ValueTemplate') is not None:
                    params.append((type_param, old_item.get('ValueTemplate')))
                elif type_param == 'colorGetterType' and old_item.get('ColorGetterType') is not None:
                    params.append((type_param, old_item.get('ColorGetterType')))
                elif type_param == 'colorGetterCode' and old_item.get('ColorGetterCode') is not None:
                    params.append((type_param, old_item.get('ColorGetterCode')))
       
        return (1, (type_name, tag_props, params))
    except Exception as ex:
        return (0, traceback.format_exc())

def get_params_form_item(meta_prop: ET.Element, old_item: ET.Element, code_field: str):

    try:
        
        uuid_item = meta_prop.get("uuid")
        
        type_name = meta_prop.find("TypeParameter").get("typeName")

        prop_params = ""
        prop_name = ""
        prop_helpText = ""

        if old_item is not None:
            attr_code = old_item.get("PropertyUUID")
            prop_params = old_item.get("Params")
            prop_name = old_item.get("Label", "") if type_name != 'ResourceLinkNETListDDT' else attr_code
            prop_helpText = old_item.get("HelpText", "")
            if attr_code in GLOBAL_COUNT_ATTRS:
                GLOBAL_COUNT_ATTRS.remove(attr_code)
        else:
            prop_name = meta_prop.find("TypeParameter").get("description")
            attr_code = meta_prop.find("TypeParameter").get("name")
       

    
        tag_props = {
            "code": code_field,
            "formItemType": CONFIG['MAPPING_TYPE_INPUT'][type_name],
            "indentLevel": extract_param_value(prop_params, "level") or 0,
            "isEnabled": "true",
            "isService": "false",
            "name": prop_name,
            "helpText":  prop_helpText,
            "target": "ENTITY_PAGE,FORM",
            "uuid": uuid_item
        }

        if type_name != 'ResourceLinkNETListDDT':
            tag_props['sourceType'] = 'ATTRIBUTE'

        if type_name[-1] == 'D':
            meta_prop.find("TypeParameter").set("typeName", '')

        params = []
        # APP.log(type_name)
        for type_param in CONFIG['MAPPING_PARAMETRS'][type_name]:
            if type_param == 'maxRows':
                params.append((type_param, extract_param_value(prop_params, "maxVisibleRows") or 1))
            elif type_param == 'dictionaryType':
                # APP.log(meta_prop.find("TypeParameter").get("resourceName"))
                j = meta_prop.find("TypeParameter").get("resourceName").split('-')[1]
                # APP.log(ET.tostring(meta_prop))
                # APP.log("Зависимый справочник:", j)
                GLOBAL_SET_JOURNALS.add(j)
                params.append((type_param, j))
            elif type_param == 'journalCode':
                # APP.log(meta_prop.find("TypeParameter").get("resourceName"))
                j = meta_prop.find("TypeParameter").get("resourceName")
                # APP.log(ET.tostring(meta_prop))
                # APP.log("Зависимый справочник:", j)
                # GLOBAL_SET_JOURNALS.add(j)
                if j in CONFIG['MAPPING_JOURNALS']:
                    params.append((type_param, CONFIG['MAPPING_JOURNALS'][j]))
                else:
                    APP.log(f"Ошибка: заполните full_config.json 'MAPPING_JOURNALS', ключом {j}", "red")
            elif type_param == 'needShowFileDescriptionRows':
                params.append((type_param, 'true'))
            elif type_param == 'isOpen':
                params.append((type_param, 'true'))
            elif type_param == 'enableObjectCreation':
                params.append((type_param, 'true'))
       
        return (1, (type_name, tag_props, params))
    except Exception as ex:
        return (0, traceback.format_exc())

def get_type_param_attrs_meta_property(root: ET.Element):
    try:
        # APP.log(ET.tostring(root))
        uuid_source = root.attrib.get('UUID')
        name = root.attrib.get('Name')
        required = root.attrib.get('Required')
        type_param_attrs = {
            'description': name,
            'name': uuid_source,
            'required': required,
        }
        GLOBAL_COUNT_ATTRS.append(uuid_source)
        type_tag = None
        type_elem = None
    
        for t in CONFIG['POSSIBLE_TYPES']:
            elem = root.find(t)
            if elem is not None:
                type_tag = t
                type_elem = elem
                break
        # APP.log(type_tag)

        for key, elem in CONFIG['MAPPING_TYPES'][type_tag].items():
            if key == 'New':
                for prop, val in elem:
                    type_param_attrs[prop] = val
                continue
            elif key == 'toForm':
                for key_prop in elem:
                    new_val = type_elem.find(key_prop)
                    if new_val is not None:
                        if uuid_source not in GLOBAL_LIST_FORM_PROP:
                            GLOBAL_LIST_FORM_PROP[uuid_source] = [(key_prop, new_val)]
                        else:
                            GLOBAL_LIST_FORM_PROP[uuid_source].append((key_prop, new_val))
                continue
            new_val = type_elem.find(key)
            if type_tag in (CONFIG['POSSIBLE_TYPES'][12], CONFIG['POSSIBLE_TYPES'][13]):
                new_val = type_elem.find('Date').find(key)
            # try:
            if new_val is not None:
                if key == 'Data':
                    # APP.log(new_val.text)
                    if new_val.text in CONFIG['MAPPING_RESOURCE_NAME']:
                        type_param_attrs[elem[0]] = CONFIG['MAPPING_RESOURCE_NAME'][new_val.text]
                    else:
                        APP.log(f'Ошибка: заполните full_config.json "MAPPING_RESOURCE_NAME", ключом {new_val.text}', "red")
                elif key == 'DictionaryCode':
                    type_param_attrs[elem[0]] = 'dictionary-' + new_val.text
                elif key == 'MaxSize' and new_val.text == '0':
                    pass
                elif key == 'MaxSize' and new_val.text == '0':
                    pass
                elif key == 'EntityType':
                    type_param_attrs[elem[0]] = to_snake_case(new_val.text)
                else:
                    type_param_attrs[elem[0]] = new_val.text
                
            elif elem[1] is not None:
                type_param_attrs[elem[0]] = elem[1]
            # except Exception as ex:
            #    # APP.log(ex, key, elem)
        
        if root.tag in (CONFIG['MAIN_TAG_TYPES'][0], CONFIG['MAIN_TAG_TYPES'][3]):
            type_param_attrs['typeName'] = CONFIG['MAPPING_TYPE_NAME_ITEM'][type_tag]
        elif root.tag == CONFIG['MAIN_TAG_TYPES'][1]:
            # APP.log('НАДО ЗАПОЛНИТЬ CONFIG['MAPPING_TYPES_NAME_RANGE']')
            type_param_attrs['typeName'] = CONFIG['MAPPING_TYPES_NAME_RANGE'][type_tag]
        elif  root.tag == CONFIG['MAIN_TAG_TYPES'][2]:
            type_param_attrs['typeName'] = CONFIG['MAPPING_TYPES_NAME_LIST'][type_tag]
        return (1, type_param_attrs)
    except Exception as ex:
        return (0, traceback.format_exc())

def gen_form_item(old_item: ET.Element, meta_prop: ET.Element, field_code:str, params:list=None):
    if params is None:
        ans_param = get_params_form_item(meta_prop, old_item, field_code)
    else:
        ans_param = (1, params)
    if ans_param[0]:
        ans_atr = generate_new_form_item_migration(*ans_param[1])
        if ans_atr[0]:
            return ans_atr[1]
        else:
            APP.log(f'Ошибка: создание элемента формы произошло с ошибкой: {ans_atr[1]}', "red")
    else:
        APP.log(f'Ошибка: создание параметров для элемента формы произошло с ошибкой:{ans_param[1]}', 'red')
    return None

def gen_transient_form_item(old_item: ET.Element, code_field: str):
    ans_param = get_params_transient_form_item(old_item, code_field)
    if ans_param[0]:
        ans_atr = generate_new_form_item_migration(*ans_param[1])
        if ans_atr[0]:
            return ans_atr[1]
        else:
            APP.log(f'Ошибка: создание вычисляемого элемента формы произошло с ошибкой: {ans_atr[1]}', 'red')
    else:
        APP.log(f'Ошибка: создание параметров вычисляемого элемента формы произошло с ошибкой: {ans_param[1]}', 'red')
    return None

def gen_meta_attribute(old_tag: ET.Element):
    ans_param = get_type_param_attrs_meta_property(old_tag)
    if ans_param[0]:
        ans_atr = generate_new_meta_attribute_migration(ans_param[1])
        if ans_atr[0]:
            return ans_atr[1]
        else:
            APP.log(f'Ошибка: создание схемы атрибута произошло с ошибкой: {ans_atr[1]}', 'red')
    else:
        APP.log(f'Ошибка: создание параметров для схемы атрибута произошло с ошибкой: {ans_param[1]}', 'red')
    return None

def migrate_group_form(old_group: ET.Element, properties: ET.Element, code_section: str):
    new_root = None
    section_group = None
    # APP.log(old_group.get("Label"))
    if old_group.get("NonGrouped") == "true":
        new_root = ET.Element('SectionItems')
    else:
        section_group =  ET.Element('SectionGroup', {'name': old_group.get("Label") or "", 'code': code_section, "isOpen": old_group.get("Revealed") or "",})
        new_root = ET.Element('GroupItems')

    # можно добавить TransientItem, ButtonItem ...
    for num, old_item in enumerate(old_group):
        if old_item.tag == 'FormItem':
            code_item = old_item.get("PropertyUUID")
            schema_attribute = None
            params = None
            if code_item is not None:
                schema_attribute = get_attribute_by_code(properties, code_item)
            else:
                params = ('Label', {"code": code_section + '_field' + str(num), "formItemType": "StaticLabel", "indentLevel":"0", "isEnabled":"true", "isService":"false", "name": old_item.get("Label"), "target":"ENTITY_PAGE,FORM"}, [])
            new_root.append(gen_form_item(old_item, meta_prop=schema_attribute, field_code=code_section + '_field' + str(num), params=params))
        elif old_item.tag == 'TransientItem' or old_item.tag == 'ButtonItem':
            name_el = "_____"
            if old_item.get("Name"):
                name_el = old_item.get("Name")
            elif old_item.get("Label"):
                name_el = old_item.get("Label")
            APP.log(f'Внимание: при конфигурации обнаружен: {old_item.tag}, следует проверить данный элемент "{name_el}"', 'orange')
            new_root.append(gen_transient_form_item(old_item, code_section + '_field' + str(num)))
        elif "OOC" in old_item.tag:
            if old_item.tag in CONFIG["MAPPING_SYSTEM_FIELDS"]:
                if old_item.get("Hidden") != "false": continue
                system_item = ET.fromstring(CONFIG["MAPPING_SYSTEM_FIELDS"][old_item.tag])
                new_root.append(system_item)
                if old_item.tag in CONFIG["REQUIRED_SYSTEM_FIELDS"]:
                    GLOBAL_LIST_FORM_PROP[old_item.tag] = old_item.get("DefaultValue")
                if old_item.tag in CONFIG["MAPPING_EXTENSIONS"]:
                    GLOBAL_EXTENSIONS.add(CONFIG["MAPPING_EXTENSIONS"][old_item.tag])
            else:
                APP.log(f"Ошибка, заполните full_config.json 'MAPPING_SYSTEM_FIELDS', ключом {old_item.tag}", 'red')
        else:
            APP.log(f'Ошибка: был пропущен элемент формы: {old_item.tag}', 'red')
    
    if section_group is not None:
        section_group.append(new_root)
        return section_group
            
    return new_root

def meta_migrate_properties(properties: ET.Element):
    new_root = ET.Element('MetaEntityVersion', {'orderNumber': 1, 'uuid': gen_uuid()})
    # APP.log('!A!A!A!!A!!A!A!A!A', properties.findall(tag))
    for meta in properties:
        attr = gen_meta_attribute(meta)
        # APP.log('!!!!!!!!!!!!!!!!!!!!', attr)
        new_root.append(attr)
    return new_root


def generate_dynamic_form_migrate(source_xml: str, uuid_conf: str, new_attributes: ET.Element, type_entity_name: str):

    if type_entity_name == CONFIG['PROPERTIES_TYPE_ENTITY'][0]:
        old_root = ET.fromstring(source_xml).find('Items').find("EntityType")
        entity_name = to_snake_case(old_root.find("Uuid").text)
    elif type_entity_name == CONFIG['PROPERTIES_TYPE_ENTITY'][1]:
         old_root = ET.fromstring(source_xml)
         entity_name = to_snake_case(old_root.find("TypeID").text)
         
    else:
        APP.log(f"Ошибка: недопустимый тип сущности: {type_entity_name}", 'red')

    new_root = ET.Element('Data')
    root_schema = ET.Element('DynamicForm', {'name': entity_name, "staticFormObjectType": CONFIG['MAPPING_ENTITIES_NAME_FORM'][type_entity_name], 'uuid': uuid_conf})

    for num_tab, tab in enumerate(old_root.find(CONFIG['MAPPING_NAME_CONSTRUCTOR'][type_entity_name])):
        if tab.tag == 'FunctionalTab':
            new_func_tab = ET.Element('FormTab', {'name': tab.get("Label"), "code": "tab" + str(num_tab), 'type': CONFIG['MAPPING_FUNCTIONAL_TAB'][tab.get("Type")]})
            root_schema.append(new_func_tab)
        elif tab.tag == 'CustomTab':
            new_custom_tab = ET.Element('FormTab', {'name': tab.get("Label"), "code": tab.get("Alias").replace('-', "_") if tab.get("Alias") is not None else "tab" + str(num_tab), 'type': "CUSTOM", "icon": tab.get("Icon") or 'view_list'})
            for num_section, section in enumerate(tab):
                new_section = ET.Element('TabSection', {'name': section.get("Label") or 'Секция ' + str(num_section), "code": new_custom_tab.get("code") + "_section" + str(num_section)})
                for num, group in enumerate(section):
                    new_group = migrate_group_form(group, new_attributes, new_section.get('code') + '_group' + str(num))
                    new_section.append(new_group)
                new_custom_tab.append(new_section)
            root_schema.append(new_custom_tab)
        else:
            APP.log(f"Ошибка: недопустимый тип вкладки: {tab.tag}", 'red')
    
    if len(GLOBAL_COUNT_ATTRS):
        new_custom_tab = ET.Element('FormTab', {'name': 'Служебная вкладка', "code": 'additional_tab', 'type': "CUSTOM", "icon": 'file_hidden'})
        new_section = ET.Element('TabSection', {'name': 'Секция 1', "code": "additional_tab_section1"})

        new_root_section = ET.Element('SectionItems')

        for num, code_item in enumerate(GLOBAL_COUNT_ATTRS):
            
            schema_attribute = get_attribute_by_code(new_attributes, code_item)
            
            new_root_section.append(gen_form_item(None, field_code=f"additional_tab_section1_field{num}", meta_prop=schema_attribute))
            # APP.log(ET.tostring(new_root_section))
            
        new_section.append(new_root_section)
        new_custom_tab.append(new_section)
        root_schema.append(new_custom_tab)

    
    if type_entity_name == CONFIG['PROPERTIES_TYPE_ENTITY'][0]:
        column_definitions = old_root.find("ColumnDefinitions")
        new_journal_definition = ET.Element('JournalDefinition', {'showRowNumbers': column_definitions.get("ShowRowNumbers")})
        for old_column in column_definitions:
            new_column =  ET.Element('ColumnDefinition')

            header =  ET.Element('Header')
            header.text = old_column.find("Header").text
            new_column.append(header)

            code =  ET.Element('Code')
            code.text = old_column.find("Field").text.replace("{", "").replace("}", "")
            new_column.append(code)

            width =  ET.Element('Width')
            old_width = old_column.find("Width")
            width.text = old_width.text if old_width is not None else '100'
            new_column.append(width)
            
            sortable =  ET.Element('Sortable')
            old_sortable = old_column.find("Sortable")
            sortable.text = old_sortable.text if old_sortable is not None else 'false'
            new_column.append(sortable)

            field =  ET.Element('Field')
            code_atr = old_column.find("Field").text
            if '{' == code_atr[0]:
                # APP.log(old_column.find("Field").text)
                item_uuid = get_attribute_by_code(new_attributes, old_column.find("Field").text[1:-1]).get("uuid")
                item_code = ["{" + elem.get("code") + "}" for elem in root_schema.iter() if elem.attrib.get('uuid') == item_uuid][0]
                field.text = item_code
            else:
                uuid_item = get_attribute_by_code(new_attributes, code_atr).get('uuid')
                field.text = uuid_item
            new_column.append(field)

            sort_direction =  ET.Element('SortDirection')
            old_sort_dir = old_column.find("SortDirection")
            sort_direction.text = old_sort_dir.text if old_sort_dir is not None else 'ASC'
            new_column.append(sort_direction)

            sort_order =  ET.Element('SortOrder')
            old_sort_order = old_column.find("SortOrder")
            sort_order.text =  old_sort_order.text if old_sort_order is not None else '-1'
            new_column.append(sort_order)

            type_c =  ET.Element('Type')
            old_type = old_column.find("Type")
            type_c.text = old_type.text if old_type.text == 'LinkTemplate' else ''
            new_column.append(type_c)

            searchable =  ET.Element('Searchable')
            searchable.text = "false"
            new_column.append(searchable)

            render_params =  ET.Element('RenderParams')
            
            for param in old_column.find("RenderParams"):
                
                new_param = ET.Element('RenderParam')

                label_template =  ET.Element('Name')
                label_template.text = param.tag
                new_param.append(label_template)

                label_template =  ET.Element('Value')
                label_template.text = param.text
                new_param.append(label_template)

                render_params.append(new_param)

            new_column.append(render_params)

            new_journal_definition.append(new_column)
        root_schema.append(new_journal_definition)
    
    new_root.append(root_schema)

    return new_root, entity_name


def generate_meta_migrate(source_xml: str, uuid_conf: str):
    old_root = ET.fromstring(source_xml)
    type_entity_name = old_root.find('ObjectType').text
    name_entity = old_root.find('Name').text
    properties = old_root.find('Properties')

    new_root = ET.Element('Data')
    root_schema = ET.Element('MetaEntitySchema', {'type': CONFIG['MAPPING_ENTITIES_NAME'][type_entity_name], 'uuid': uuid_conf, 'name': name_entity})
    new_schema = meta_migrate_properties(properties)
    # APP.log(new_schema)
    root_schema.append(new_schema)
    new_root.append(root_schema)

    return (new_root, type_entity_name, new_schema)
            

def generate_type_datatype(source_xml: str, type_entity_name: str, uuid_conf: str):
    if type_entity_name == CONFIG['PROPERTIES_TYPE_ENTITY'][0]:

        old_root = ET.fromstring(source_xml).find('Items').find("EntityType")
        type_root = ET.Element('Data')
        nested_entity_type = ET.Element('NestedEntityType', {'code': to_snake_case(old_root.find('Uuid').text), 'name': old_root.find('Name').text})
        type_root.append(nested_entity_type)

        data_type_root = ET.Element('Data')
        nested_entity_type_data = ET.Element('NestedEntityTypeData', {'type': nested_entity_type.get('code')})
        meta_entity =  ET.Element('MetaEntity')
        uuid_ent = ET.Element('UUID')
        uuid_ent.text = uuid_conf
        meta_entity.append(uuid_ent)
        nested_entity_type_data.append(meta_entity)
        data_type_root.append(nested_entity_type_data)

        return type_root, data_type_root
    
    elif type_entity_name == CONFIG['PROPERTIES_TYPE_ENTITY'][1]:

        old_root = ET.fromstring(source_xml)
        type_root = ET.Element('Data')
        ooc_type = ET.Element('ControlObjectType', {'code': to_snake_case(old_root.find('TypeID').text),
                                                     'name': old_root.find('ObjectTypeName').text, 'isEnabled': old_root.find('Enabled').text,
                                                       "shortName": GLOBAL_LIST_FORM_PROP["OOCShortName"] if "OOCShortName" in GLOBAL_LIST_FORM_PROP and GLOBAL_LIST_FORM_PROP["OOCShortName"] is not None else "no_name",
                                                         'useInControlObjectJournalFilter': old_root.find('UseInControlObjectJournalFilter').text})
        type_root.append(ooc_type)

        data_type_root = ET.Element('Data')
        ooc_type_data = ET.Element('ControlObjectTypeData', {'type': ooc_type.get('code')})

        extensions = ET.Element('Extensions')
        for ext in GLOBAL_EXTENSIONS:
            extension = ET.Element('Extension')
            extension.text = ext
            extensions.append(extension)
        
        ooc_type_data.append(extensions)

        meta_entity =  ET.Element('MetaEntity')
        uuid_ent = ET.Element('UUID')
        uuid_ent.text = uuid_conf
        meta_entity.append(uuid_ent)
        ooc_type_data.append(meta_entity)

        cost = GLOBAL_LIST_FORM_PROP["OOCCost"] if "OOCCost" in GLOBAL_LIST_FORM_PROP and GLOBAL_LIST_FORM_PROP["OOCCost"] is not None else "1"
        curator = GLOBAL_LIST_FORM_PROP["OOCCurator"] if "OOCCurator" in GLOBAL_LIST_FORM_PROP and GLOBAL_LIST_FORM_PROP["OOCCurator"] is not None else "eta_appadmin"
        # periodStart = GLOBAL_LIST_FORM_PROP["OOCPeriod"].split(",")[0] if "OOCPeriod" in GLOBAL_LIST_FORM_PROP and GLOBAL_LIST_FORM_PROP["OOCPeriod"] is not None else "CURRENT_YEAR_START_DATE"
        # periodEnd = GLOBAL_LIST_FORM_PROP["OOCPeriod"].split(",")[1] if "OOCPeriod" in GLOBAL_LIST_FORM_PROP and GLOBAL_LIST_FORM_PROP["OOCPeriod"] is not None else "CURRENT_YEAR_START_DATE"
        periodStart = "CURRENT_YEAR_START_DATE"
        periodEnd = "CURRENT_YEAR_START_DATE"


        def_vals = ET.fromstring(f'''    <DefaultValues>
      <DefaultValue fieldName="cost">{cost}</DefaultValue>
      <DefaultFunction fieldName="periodStart">{periodStart}</DefaultFunction>
      <DefaultFunction fieldName="periodEnd">{periodEnd}</DefaultFunction>
      <DefaultObject fieldName="curator" objectField="USER_NAME">{curator}</DefaultObject>
    </DefaultValues>
''')
        ooc_type_data.append(def_vals)
        data_type_root.append(ooc_type_data)

        return type_root, data_type_root

    else:
        APP.log(f"Ошибка: недопустимый тип сущности: {type_entity_name}", 'red')
        return None, None


def generate_config_manifest(place:str, type_ent:str):
       with open(resource_path(place), 'w', encoding='utf-8') as f:
            f.write(CONFIG['MAPPING_MANiFEST'][type_ent])

def append_config_manifest(path:str, type_ent:str, name_ent:str, old_code:int):
    tree = ET.parse(os.path.join(path, 'config-manifest.xml'))

    # root_export = tree.getroot().find("ExportData")
    # filter_type = root_export.findall(f'.//CompareDataFilter[@id="{CONFIG['MAPPING_FILENAME'][type_ent]}Filter"]')[0]
    # for el in filter_type:
    #     if el.text == name_ent:
    #         return
    # string_filter_value = ET.Element("StringFilterValue")
    # string_filter_value.text = name_ent
    # filter_type.append(string_filter_value)

    root = tree.getroot().find("ConfigItems")
    if len(root.findall(f'.//DirectoryConfigItem[@id="metaEntitySchema{old_code}"]')):
        return
    last_id = root[-1].get("id")
    export_type = CONFIG['MAPPING_FILENAME'][type_ent][0].upper() + CONFIG['MAPPING_FILENAME'][type_ent][1:]
    export_name = CONFIG['MAPPING_FILENAME'][type_ent]
    append_items = [f'''
<DirectoryConfigItem id="nestedEntityType{old_code}" dependsOn="{last_id}">
<Directory>/{name_ent}/{export_name}</Directory>
<Export>
    <Type name="{export_type}">
    <ExportData filterBlocksJoinPolicy="OR">
    <Filters>
      <CompareDataFilter id="{export_name}Filter" name="{export_type}Code" joinPolicy="OR">
        <StringFilterValue>{name_ent}</StringFilterValue>
      </CompareDataFilter>
    </Filters>
    <FilterBlocks>
      <FilterBlock joinPolicy="OR">
        <ClassNames>
          <ClassName>{export_type}</ClassName>
        </ClassNames>
        <Filter>{export_name}Filter</Filter>
      </FilterBlock>
    </FilterBlocks>
  </ExportData>
  </Type>
</Export>
</DirectoryConfigItem>''',
f'''<DirectoryConfigItem id="metaEntitySchema{old_code}" dependsOn="nestedEntityType{old_code}">
<Directory>/{name_ent}/metaEntitySchema</Directory>
<Export>
    <Type name="MetaEntitySchema">
    <ExportData filterBlocksJoinPolicy="OR">
    <Filters>
      <CompareDataFilter id="{export_name}Filter" name="{export_type}Code" joinPolicy="OR">
        <StringFilterValue>{name_ent}</StringFilterValue>
      </CompareDataFilter>
    </Filters>
    <FilterBlocks>
      <FilterBlock joinPolicy="OR">
        <ClassNames>
          <ClassName>MetaEntity</ClassName>
        </ClassNames>
        <Filter>{export_name}Filter</Filter>
      </FilterBlock>
    </FilterBlocks>
  </ExportData>
    </Type>
</Export>
</DirectoryConfigItem>''',
f'''<DirectoryConfigItem id="nestedEntityTypeData{old_code}" dependsOn="metaEntitySchema{old_code}">
<Directory>/{name_ent}/{export_name}Data</Directory>
<Export>
    <Type name="{export_type}Data">
    <ExportData filterBlocksJoinPolicy="OR">
    <Filters>
      <CompareDataFilter id="{export_name}Filter" name="{export_type}Code" joinPolicy="OR">
        <StringFilterValue>{name_ent}</StringFilterValue>
      </CompareDataFilter>
    </Filters>
    <FilterBlocks>
      <FilterBlock joinPolicy="OR">
        <ClassNames>
          <ClassName>{export_type}</ClassName>
        </ClassNames>
        <Filter>{export_name}Filter</Filter>
      </FilterBlock>
    </FilterBlocks>
  </ExportData>
    </Type>
</Export>
</DirectoryConfigItem>''',
f'''<DirectoryConfigItem id="dynamicForm{old_code}" dependsOn="nestedEntityTypeData{old_code}">
<Directory>/{name_ent}/dynamicForm</Directory>
<Export>
    <Type name="DynamicForm">
    <ExportData filterBlocksJoinPolicy="OR">
    <Filters>
      <CompareDataFilter id="{export_name}Filter" name="{export_type}Code" joinPolicy="OR">
        <StringFilterValue>{name_ent}</StringFilterValue>
      </CompareDataFilter>
    </Filters>
    <FilterBlocks>
      <FilterBlock joinPolicy="OR">
        <ClassNames>
          <ClassName>FormDefinition</ClassName>
        </ClassNames>
        <Filter>{export_name}Filter</Filter>
      </FilterBlock>
    </FilterBlocks>
  </ExportData>
    </Type>
</Export>
</DirectoryConfigItem>'''] 

    for el in append_items:
        item = ET.fromstring(el)
        root.append(item)
    
    

    tree.write(os.path.join(path, 'config-manifest.xml'), encoding="utf-8", xml_declaration=True)

def clear_folder(folder_path):
    if not os.path.exists(folder_path):
        APP.log(f"Уведомление: Папка {folder_path} не существует — пропускаем очистку.")
        return

    if not os.path.isdir(folder_path):
        APP.log(f"Ошибка: указанный путь не является папкой: {folder_path}", 'red')
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # удалить файл или символическую ссылку
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # удалить папку и её содержимое
        except Exception as e:
            APP.log(f"Ошибка: ошибка при удалении {file_path}: {e}", 'red')

def convert_dictionary_to_user_dict(dictionary):
    user_dict = ET.Element('UserDictionary', {
        'code': dictionary.attrib['Code'],
        'description': dictionary.attrib['Name'],
        'lineStartSearching': 'false',
        'name': dictionary.attrib['Name'],
        'sortField': 'orderIndex'
    })

    for value in dictionary.findall('Value'):
        code = value.attrib['Code']
        name = value.attrib['Name']
        if code == "5":
            continue  # Пропустить значение с Code="5"
        ET.SubElement(user_dict, 'Item', {'code': code, 'name': name})

    return user_dict

def append_to_existing_file(existing_file, new_user_dicts):
    try:
        tree = ET.parse(existing_file)
        root = tree.getroot()
        if root.tag != 'Data':
            APP.log("Ошибка: корневой тег в целевом файле должен быть <Data>", "red")
            return

        for user_dict in new_user_dicts:
            root.append(user_dict)

        tree.write(existing_file, encoding="utf-8", xml_declaration=True)
        # APP.log(f"XML успешно обновлён: {existing_file}", "red")

    except Exception as e:
        APP.log(f"Ошибка при обновлении файла: {e}", "red")

def generate_directory(output_directory: str, type_entity_name: str, input_dictionary:str):
    clear_folder(output_directory)
    output_form = os.path.join(output_directory, 'dynamicForm', 'dynamicForm.xml')
    output_schema = os.path.join(output_directory, 'metaEntitySchema', 'metaEntitySchema.xml')
    output_type = os.path.join(output_directory, f'{CONFIG['MAPPING_FILENAME'][type_entity_name]}', f'{CONFIG['MAPPING_FILENAME'][type_entity_name]}.xml')
    output_type_data = os.path.join(output_directory, f'{CONFIG['MAPPING_FILENAME'][type_entity_name]}Data', f'{CONFIG['MAPPING_FILENAME'][type_entity_name]}Data.xml')

    output_files = [output_form, output_schema, output_type, output_type_data]
    # Создание всех необходимых директорий  
    for file_path in output_files:
        dir_path = os.path.dirname(file_path)
        os.makedirs(dir_path, exist_ok=True)  # создаст директорию, если она ещё не существует

    for file_path in output_files:
        with open(resource_path(file_path), 'w', encoding='utf-8') as f:
            f.write('') 
    
    generate_config_manifest(os.path.join(output_directory, 'config-manifest.xml'), type_entity_name)
    with open(resource_path(os.path.join(output_directory, 'СПРАВОЧНИКИ.txt')), 'w', encoding='utf-8') as f:
        for j in GLOBAL_SET_JOURNALS:
            if has_user_dictionary_with_code(APP.PATH_TO_DICT, j):
                APP.log(f"Требуемый справочник (присутствует в dicts): {j}", 'green')
            elif j in CONFIG["SYSTEM_DICTIONARY"]:
                APP.log(f"Требуемый справочник (системный): {j}", 'green')
            elif input_dictionary is not None:
                try:
                    input_tree = ET.parse(input_dictionary)
                    input_root = input_tree.getroot()

                    dictionaries = input_root.findall(f'.//DictionaryTypeDTO[@Code="{j}"]')
                    if not dictionaries:
                        APP.log(f"Требуемый справочник (отсутствует в dicts): {j}", 'red')
                    else:
                        new_user_dicts = [convert_dictionary_to_user_dict(d) for d in dictionaries]
                        append_to_existing_file(APP.PATH_TO_DICT, new_user_dicts)
                        APP.log(f"Требуемый справочник (присутствует в dicts): {j}", 'green')
                except ET.ParseError as e:
                    APP.log(f"Ошибка разбора XML: {e}", "red")
            else:
                 APP.log(f"Требуемый справочник (отсутствует в dicts): {j}", 'red')
            f.write(f"Требуемый справочник: {j}\n")
    
    return output_form, output_schema, output_type, output_type_data

def main(input_form:str, input_schema:str, output_directory:str, old_code:int, input_dictionary:str):
    with open(resource_path(input_schema), "r", encoding="utf-8") as f:
        old_schema = f.read()
    
    uuid_conf = gen_uuid()

    new_schema, type_entity_name, new_attributes = generate_meta_migrate(old_schema, uuid_conf)

    # APP.log(new_attributes.text)

    with open(resource_path(input_form), "r", encoding="utf-8") as f:
        old_form = f.read()
    
    new_form, code_ent = generate_dynamic_form_migrate(old_form, uuid_conf, new_attributes, type_entity_name)

    type_root, data_type_root = generate_type_datatype(old_form, type_entity_name, uuid_conf)

    append_config_manifest(output_directory, type_entity_name, code_ent, old_code)

    output_directory = os.path.join(output_directory, f'{code_ent}') + os.sep

    output_form, output_schema, output_type, output_type_data = generate_directory(output_directory, type_entity_name, input_dictionary)

    crutch_typename(new_schema)
    tree_schema = ET.ElementTree(new_schema)
    stringify_attributes(new_schema)
    tree_schema.write(output_schema, encoding="utf-8", xml_declaration=True)

    tree_form = ET.ElementTree(new_form)
    stringify_attributes(new_form)
    tree_form.write(output_form, encoding="utf-8", xml_declaration=True)

    tree_type = ET.ElementTree(type_root)
    stringify_attributes(type_root)
    tree_type.write(output_type, encoding="utf-8", xml_declaration=True)

    tree_data_type = ET.ElementTree(data_type_root)
    stringify_attributes(data_type_root)
    tree_data_type.write(output_type_data, encoding="utf-8", xml_declaration=True)

    GLOBAL_SET_JOURNALS.clear()
    GLOBAL_LIST_FORM_PROP.clear()
    GLOBAL_COUNT_ATTRS.clear()
 
    APP.log(f"Готово.", "green") 
    APP.log(f"Результаты записаны в:\n {output_form},\n {output_schema},\n {output_type},\n {output_type_data}")


class SimpleApp:
    SAVED_FILE = "saved.json"
    # HISTORY_FILE = "history.json"
    PATH_TO_DICT = None
    path_to_in_dict = None
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.title("Конвертер конфигураций ОК и ВлС со второго Эталона на третий")
        self.root.geometry("900x600")
        self.create_widgets()
        # self.processed_files = self.load_history()
        self.load_config()
        if len(self.get_dir2()):
            self.create_paths()
        self.PATH_TO_DICT = self.get_dir2() + "\\dicts\\userDictionary\\userDictionary.xml"
        
        

    def create_widgets(self):
        # Директория 1
        tk.Label(self.root, text="Входная директория:").pack(anchor='w', padx=10, pady=5)
        frame1 = tk.Frame(self.root)
        frame1.pack(fill='x', padx=10)
        self.dir1_entry = tk.Entry(frame1)
        self.dir1_entry.pack(side='left', fill='x', expand=True)
        tk.Button(frame1, text="Обзор", command=lambda: self.choose_dir(self.dir1_entry)).pack(side='right')

        # Директория 2
        tk.Label(self.root, text="Выходная директория:").pack(anchor='w', padx=10, pady=5)
        frame2 = tk.Frame(self.root)
        frame2.pack(fill='x', padx=10)
        self.dir2_entry = tk.Entry(frame2)
        self.dir2_entry.pack(side='left', fill='x', expand=True)
        tk.Button(frame2, text="Обзор", command=lambda: self.choose_dir(self.dir2_entry)).pack(side='right')

        tk.Label(self.root, text="Выберите файл из директории 1:").pack(anchor='w', padx=10, pady=5)
        self.file_combobox = ttk.Combobox(self.root, state="readonly")
        self.file_combobox.pack(fill='x', padx=10) 

        # Кнопка запуска
        tk.Button(self.root, text="Выполнить", command=self.run_action).pack(pady=10)
        tk.Button(self.root, text="Обновить маппинги", command=self.update_mappings).pack(pady=5)

        # Поле логов
        tk.Label(self.root, text="Логи:").pack(anchor='w', padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(self.root, height=10)
        self.log_text.pack(fill='both', expand=True, padx=10, pady=5)
    
    def update_mappings(self):
        try:
            with open(resource_path('full_config.json'), 'r', encoding='utf-8') as f:
                CONFIG.clear()
                CONFIG.update(json.load(f))
            self.log("Маппинги успешно обновлены", "green")
        except Exception as ex:
            self.log(traceback.format_exc(), "red")

    def choose_dir(self, entry):
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)
            self.save_config()
            if entry == self.dir1_entry:
                self.update_file_list()
                # self.clear_history()
            else:
                self.create_paths()

    def create_paths(self):
        self.PATH_TO_DICT = self.get_dir2() + "\\dicts\\userDictionary\\userDictionary.xml"
        dir_path = os.path.dirname(self.PATH_TO_DICT)
        os.makedirs(dir_path, exist_ok=True)

        conf_man_path = os.path.join(self.get_dir2(), 'dicts', 'config-manifest.xml')
        if not os.path.isfile(conf_man_path):
            with open(conf_man_path, 'w', encoding="utf-8") as file:
                file.write('''<ConfigurationManifest>
<ConfigItems type="User">
<FileConfigItem id="userDictionary">
<FileName>/userDictionary/userDictionary.xml</FileName>
</FileConfigItem>
</ConfigItems>
</ConfigurationManifest>''')
        if not os.path.isfile(self.PATH_TO_DICT):
            with open(self.PATH_TO_DICT, 'w', encoding="utf-8") as file:
                file.write('''<?xml version='1.0' encoding='utf-8'?>
<Data>
</Data>''')
        with open(os.path.join(self.get_dir2(), 'config-manifest.xml'), 'w', encoding="utf-8") as file:
            file.write('''<ConfigurationManifest>
<ConfigItems type="User">
<FileConfigItem id="userDictionary">
<FileName>dicts/userDictionary/userDictionary.xml</FileName>
</FileConfigItem>
</ConfigItems>
</ConfigurationManifest>''')


    def run_action(self):
        selected = self.file_combobox.get()
        if not selected:
            messagebox.showwarning("Нет файла", "Файл не выбран")
            return
        num = int(selected.split("№ ")[1])

        # APP.log(filename)

        # self.processed_files.add(filename)
        # self.save_history()
        # self.update_file_list()
        in_directory = self.get_dir1()
        out_directory = self.get_dir2()
        in_f = os.path.join(in_directory, f'objectType{num}.xml')
        in_s = os.path.join(in_directory, f'metaType{num}.xml')
        self.log(f"\n\nЗапуск конвертации {selected}...\n\n")
        try:  
            main(in_f, in_s, out_directory, num,self.path_to_in_dict)
        except Exception as ex:
            self.log(traceback.format_exc(), 'red')

    def get_dir1(self):
        return self.dir1_entry.get()

    def get_dir2(self):
        return self.dir2_entry.get()
    
    def log(self, message, color="black"):
        self.log_text.insert(tk.END, str(message) + "\n", color)
        self.log_text.see(tk.END)
        self.log_text.tag_config(color, foreground=color)

    def set_dir1(self, path):
        self.dir1_entry.delete(0, tk.END)
        self.dir1_entry.insert(0, path)

    def set_dir2(self, path):
        self.dir2_entry.delete(0, tk.END)
        self.dir2_entry.insert(0, path)

    def run(self):
        self.root.mainloop()

    def save_config(self):
        config = {
            "dir1": self.get_dir1(),
            "dir2": self.get_dir2()
        }
        with open(resource_path(self.SAVED_FILE), "w", encoding="utf-8") as f:
            json.dump(config, f)

    def load_config(self):
        if os.path.exists(resource_path(self.SAVED_FILE)):
            # self.log(self.SAVED_FILE)
            
            with open(resource_path(self.SAVED_FILE), "r", encoding="utf-8") as f:
                config = json.load(f)
                self.set_dir1(config.get("dir1", ""))
                self.update_file_list()
                self.set_dir2(config.get("dir2", ""))
            # self.log(self.get_dir1())
            # self.log(self.get_dir2())
    
    def update_file_list(self):
        dir1 = self.get_dir1()
        if os.path.isdir(dir1):
            files = [f for f in os.listdir(dir1) if os.path.isfile(os.path.join(dir1, f))]
            display_files = []

            for f in files:
                if "dictionary" in f: 
                    self.path_to_in_dict = os.path.join(dir1, f)
                    continue
                if 'object' not in f: continue
                full_path = os.path.join(dir1, f)

                with open(resource_path(full_path), "r", encoding="utf-8") as curr_f:
                    old_form = curr_f.read()
                    type_ent = ET.fromstring(old_form).tag
                # print(type_ent)
                name_ent = 'NestedEntity' if type_ent == 'BaseListDTO' else 'ObjectOfControl'
                # if f in self.processed_files:
                #     display_files.append(f"✓ {name_ent} № {str(f)[10:-4]}")
                # else:
                display_files.append(f"{name_ent} № {str(f)[10:-4]}")

            self.file_combobox["values"] = display_files
            if display_files:
                self.file_combobox.current(0)
        else:
            self.file_combobox["values"] = []

    # def load_history(self):
    #     if os.path.exists(self.HISTORY_FILE):
    #         with open(self.HISTORY_FILE, "r", encoding="utf-8") as f:
    #             return set(json.load(f))
    #     return set()

    # def save_history(self):
    #     with open(self.HISTORY_FILE, "w", encoding="utf-8") as f:
    #         json.dump(list(self.processed_files), f)
    
    # def clear_history(self):
    #     self.processed_files.clear()
    #     if os.path.exists(self.HISTORY_FILE):
    #         os.remove(self.HISTORY_FILE)
    #     self.update_file_list()
    #     self.log("История обработанных файлов очищена", color="red")


if __name__ == '__main__':
    APP = SimpleApp()
    APP.run()
    
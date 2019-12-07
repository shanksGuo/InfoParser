#!/usr/bin/python 
#-*- coding:utf-8 -*-

import argparse
import os
import shutil
import sys
import git
import re
reload(sys)
sys.setdefaultencoding('utf8')

class InfoLine(object):
    def __init__(self, line_number, exec_count):
        self.line_number = line_number
        self.exec_count = exec_count

class InfoFunc(object):
    def __init__(self, func_name, start_line):
        self.func_name = func_name
        self.start_line = start_line
        self.func_exec_count = 0
        self.lines = []
        self.contains_diff = False
        self.diff_lines = []

    def add_diff_line(self, line_number):
        for line_info in self.lines:
            if line_info.line_number == line_number:
                self.diff_lines.append(line_info)
                break

    def re_construct_for_diff(self):
        sorted_diff_lines = sorted(self.diff_lines, key=lambda k: k.line_number)
        if sorted_diff_lines:
            self.start_line = sorted_diff_lines[0].line_number
            self.diff_lines = sorted_diff_lines
    
    def add_line_info(self, line):
        self.lines.append(line)

class InfoRecord(object):
    def __init__(self, record_lines):
        self.record_lines = record_lines
        self.source_file = ''
        self.func_map = {}
        self.record_name = ''

    def is_record_valid(self):
        # 可能同一个.m文件产生两份数据，其中一份是冗余的
        valid = False
        for line in self.record_lines:
            if line.startswith('FN:'):
                valid = True
                break
        return valid
    
    def parse(self):
        fn_list = []
        fnda_list = []
        da_list = []
        for line in self.record_lines:
            if line.startswith('SF:'):
                self.source_file = line.split(':')[1].strip()
                head, tail = os.path.split(self.source_file)
                self.record_name = tail
            elif line.startswith('FN:'):
                fn_list.append(line.replace("FN:", ''))
            elif line.startswith('FNDA:'):
                fnda_list.append(line.replace("FNDA:", ''))
            elif line.startswith('DA:'):
                da_list.append(line.replace("DA:", ''))
        for fn in fn_list:
            func_name = fn.split(',')[1].strip()
            func_start_line = fn.split(',')[0]
            self.func_map[func_name] = InfoFunc(func_name=func_name, start_line=int(func_start_line))
        for fnda in fnda_list:
            func_name = fnda.split(',')[1].strip()
            func_exec_count = fnda.split(',')[0]
            self.func_map[func_name].func_exec_count = int(func_exec_count)
        for da in da_list:
            da_line = da.split(',')[0]
            da_exec_count = da.split(',')[1].strip()
            info_line = InfoLine(int(da_line), int(da_exec_count))
            correspond_func = self.find_func_with_line(info_line.line_number)
            correspond_func.add_line_info(info_line)

    def diff_func_list(self):
        func_list = sorted(self.func_list(), key=lambda k: k.start_line)
        result_list = []
        for func in func_list:
            if func.contains_diff:
                func.re_construct_for_diff()
                result_list.append(func)
        return result_list

    def func_number_of_hit(self, func_list):
        hit_count = 0
        for func in func_list:
            if func.func_exec_count > 0:
                hit_count += 1
        return hit_count
    
    def diff_hit_lines_count(self, func_list):
        lines_count = 0
        for func in func_list:
            for line in func.diff_lines:
                if line.exec_count > 0:
                    lines_count += 1
        return lines_count

    def diff_all_lines_count(self, func_list):
        lines_count = 0
        for func in func_list:
            lines_count += len(func.diff_lines)
        return lines_count

    def to_diff_info(self, func_list):
        if not func_list:
            return ""
        # diff_func_list = self.diff_func_list()
        temp_str = "TN:\n"
        temp_str += "SF:{}\n".format(self.source_file)
        #FN
        for func in func_list:
            temp_str += "FN:{},{}".format(func.start_line, func.func_name)
            temp_str += "\n"
        #FNDA
        for func in func_list:
            temp_str += "FNDA:{},{}".format(func.func_exec_count, func.func_name)
            temp_str += "\n"
        #FNF FNH
        temp_str += "FNF:{}".format(len(func_list))
        temp_str += "\n"
        temp_str += "FNH:{}".format(self.func_number_of_hit(func_list))
        temp_str += "\n"
        #DA
        for func in func_list:
            for line in func.diff_lines:
                temp_str += "DA:{},{}".format(line.line_number, line.exec_count)
                temp_str += "\n"
        #LF LH
        temp_str += "LF:{}".format(self.diff_all_lines_count(func_list))
        temp_str += "\n"
        temp_str += "LH:{}".format(self.diff_hit_lines_count(func_list))
        temp_str += "\n"
        temp_str += 'end_of_record\n'
        return temp_str
        
            
    def func_list(self):
        func_list = []
        for value in self.func_map.itervalues():
            func_list.append(value)
        return func_list

    def find_func_with_line(self, line_number):
        sorted_func_list = sorted(self.func_list(), key=lambda k: k.start_line, reverse=True)
        for func in sorted_func_list:
            if line_number >= func.start_line:
                return func
                break
        coverage_print("line number:{} outside all functions".format(line_number))
        return None

class InfoParser(object):
    def __init__(self, info_path):
        self.info_path = info_path

    def parse_info(self):
        with open(self.info_path) as f:
            content_lines = f.readlines()
        record_lines = []
        record_map = {}
        for line in content_lines:
            if line.startswith("end_of_record"):
                record = InfoRecord(record_lines)
                if record.is_record_valid() == True:
                    record.parse()
                    record_map[record.record_name] = record
                record_lines = []
            else:
                record_lines.append(line)
        return record_map

def readargs():
    parse = argparse.ArgumentParser()
    #生成gcno
    parse.add_argument('-ip', '--infoPath', help='bundle编译的后的normal目录', required=False)

    """
    Parse Params
    """
    return parse.parse_args()

if __name__ == '__main__':
    args = readargs()
    prase_instance = InfoParser(args.infoPath)
    result = prase_instance.parse_info()
    print result
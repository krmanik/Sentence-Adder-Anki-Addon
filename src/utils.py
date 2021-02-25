import re
hex_regex = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'

def is_hex_color(input_string):
    regexp = re.compile(hex_regex)
    if regexp.search(input_string):
        return True
    return False
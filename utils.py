def is_valid_port(port_str):
    """ Simple port validation. Returns bool """
    try:
        port = int(port_str)
        return 1 <= port <= 65535
    except ValueError:
        return False

def is_valid_ip(ip_str):
    """Simple IPv4 address validation that excludes loopback addresses. Returns bool"""
    parts = ip_str.split('.')
    # Check for standard IPv4 format and range, then exclude loopback range
    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) < 256 for part in parts):
        # Exclude loopback address range (127.x.x.x)
        if parts[0] == "127":
            return False
        return True
    return False


def to_string(input, encoding='utf-8', errors='replace'):
    """Convert Packet Payload from Bytes to String """
    if isinstance(input, str):
        return input
    elif isinstance(input, bytes):
        return input.decode(encoding, errors)
    else:
        return ""

def is_positive_number(num):
    """Returns true is given variable is a positive number"""
    try:
        num = int(num)
        return num > 0
    except ValueError as e:
        print(f"{num} is not a number: {e}")
        return False

def is_multicast(ip):
    try:
        # Convert IP address to 32-bit integer
        parts = [int(part) for part in ip.split('.')]
        if len(parts) != 4 or not all(0 <= p <= 255 for p in parts):
            return False
        return 224 <= parts[0] <= 239
    except Exception as e:
        return False
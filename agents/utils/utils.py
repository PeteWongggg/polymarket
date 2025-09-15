import json
from datetime import datetime, timezone
from typing import Optional


def parse_camel_case(key) -> str:
    output = ""
    for char in key:
        if char.isupper():
            output += " "
            output += char.lower()
        else:
            output += char
    return output


def preprocess_market_object(market_object: dict) -> dict:
    description = market_object["description"]

    for k, v in market_object.items():
        if k == "description":
            continue
        if isinstance(v, bool):
            description += (
                f' This market is{" not" if not v else ""} {parse_camel_case(k)}.'
            )

        if k in ["volume", "liquidity"]:
            description += f" This market has a current {k} of {v}."
    print("\n\ndescription:", description)

    market_object["description"] = description

    return market_object

'''
def preprocess_local_json(file_path: str, preprocessor_function: function) -> None:
    with open(file_path, "r+") as open_file:
        data = json.load(open_file)

    output = []
    for obj in data:
        preprocessed_json = preprocessor_function(obj)
        output.append(preprocessed_json)

    split_path = file_path.split(".")
    new_file_path = split_path[0] + "_preprocessed." + split_path[1]
    with open(new_file_path, "w+") as output_file:
        json.dump(output, output_file)
'''


def metadata_func(record: dict, metadata: dict) -> dict:
    print("record:", record)
    print("meta:", metadata)
    for k, v in record.items():
        metadata[k] = v

    del metadata["description"]
    del metadata["events"]

    return metadata


def parse_datetime_string(datetime_str: str) -> Optional[datetime]:
    """
    解析日期时间字符串，支持多种格式
    
    Args:
        datetime_str: 日期时间字符串
        
    Returns:
        解析后的datetime对象，如果解析失败返回None
    """
    if not datetime_str:
        return None
    
    # 常见的日期时间格式
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO格式带微秒
        "%Y-%m-%dT%H:%M:%SZ",     # ISO格式不带微秒
        "%Y-%m-%dT%H:%M:%S.%f%z", # ISO格式带时区
        "%Y-%m-%dT%H:%M:%S%z",    # ISO格式带时区
        "%Y-%m-%d %H:%M:%S",      # 简单格式
        "%Y-%m-%d",               # 只有日期
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            # 如果没有时区信息，假设为UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None


def is_market_close_within_buffer(market_end_date: str, buffer_minutes: float) -> bool:
    """
    检查市场关闭时间是否在缓冲时间内
    
    Args:
        market_end_date: 市场结束日期字符串
        buffer_minutes: 缓冲时间（分钟）
        
    Returns:
        True如果市场在缓冲时间内关闭，False否则
    """
    if not market_end_date:
        return False
    
    # 解析市场结束时间
    end_datetime = parse_datetime_string(market_end_date)
    if not end_datetime:
        print(f"警告: 无法解析市场结束时间: {market_end_date}")
        return False
    
    # 获取当前UTC时间
    current_time = datetime.now(timezone.utc)
    
    # 计算时间差
    time_diff = end_datetime - current_time
    time_diff_minutes = time_diff.total_seconds() / 60
    
    # 检查是否在缓冲时间内
    is_within_buffer = time_diff_minutes <= buffer_minutes
    
    print(f"    市场关闭时间: {end_datetime}")
    print(f"    缓冲时间阈值: {buffer_minutes} 分钟")
    print(f"    当前时间: {current_time}")
    print(f"    时间差: {time_diff_minutes:.2f} 分钟")
    print(f"    是否在缓冲时间内: {is_within_buffer}")
    
    return is_within_buffer


def should_skip_trading_due_to_time_buffer(market_end_date: str, buffer_minutes: float) -> bool:
    """
    判断是否应该因为时间缓冲而跳过交易
    
    Args:
        market_end_date: 市场结束日期字符串
        buffer_minutes: 缓冲时间（分钟）
        
    Returns:
        True如果应该跳过交易，False如果可以进行交易
    """
    return is_market_close_within_buffer(market_end_date, buffer_minutes)

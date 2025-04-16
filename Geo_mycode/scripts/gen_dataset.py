"""
数据集转化文件
源文件为：
tmp_ip_anl_geo_ping_{date}.csv

被探测ip、探测点ip、时延 （ms） 、ttl、探测点region、序号 （按时延排序） 无意义，需要自己生成
anchor_id, probe_id, rtt, ttl, region, label

被探测ip、探测点ip 所在的 城市&经纬度: 通过ipinfo api获得

每个被探测ip ，都分别在 美国的10个不同的州的某个城市 进行了探测
"""


"""
需要生成数据：
probes.json (所有探测点集合)
address_v4,geometry:{type:"Point",coordinates:[4,52]},id,is_anchor

anchors.json （所有被探测点集合）
address_v4,geometry:{type:"Point",coordinates:[4,52]},id,is_anchor

ping_to_anchors.csv （所有探测点到所有被探测点的时延及相关数据） 
src,dst,prb_id,min_rtt
"""

import pandas as pd
import requests
import json
from collections import defaultdict

DATR_DIR = "/home/lzj/geoloc-imc-2023/Geo_mycode/data"

import ipinfo
access_token = 'd4eee514558608' # 付费



def gen_id(dataset_raw):
    # 被探测点id
    anchors_ids = dataset_raw['anchor_ad'].unique().tolist()
    anchors_ids_dict = {anchors_ids[i]: i for i in range(len(anchors_ids))}
    
    probes_ids = dataset_raw['probe_ad'].unique().tolist()
    probes_ids_dict = {probes_ids[i]: i for i in range(len(probes_ids))}

    return anchors_ids_dict, probes_ids_dict

def ipinfo_api(ipv4_address):
    try:
        handler = ipinfo.getHandler(access_token)
        details = handler.getDetails(ipv4_address)
        loc = details.loc
        longtitude = loc.split(',')[0]
        longtitude = float(longtitude)
        longtitude = round(longtitude, 4)

        langtitude = loc.split(',')[1]
        langtitude = float(langtitude)
        langtitude = round(langtitude, 4)

        country_code = details.country
        asn_v4 = details.asn['asn'].replace('AS', '')
        

        return longtitude, langtitude, details.city, country_code, asn_v4
    except Exception as e:
        print(f"Error fetching IP info for {ipv4_address}: {e}")
        raise ValueError(e)
        

def gen_probes_anchors_json(dataset_raw):
    global anchors_ids_dict
    global probes_ids_dict
    anchors_ids_dict, probes_ids_dict = gen_id(dataset_raw)
    
    # id添加到 dataset_raw 中
    dataset_raw['anchor_id'] = dataset_raw['anchor_ad'].map(anchors_ids_dict)
    dataset_raw['probe_id'] = dataset_raw['probe_ad'].map(probes_ids_dict)

    # 获取地理位置信息
    anchor_geos = {}
    probe_geos = {}

    print("probes begin!")
    for ip in probes_ids_dict.keys():
        lon, lat, city,country_code,asn_v4 = ipinfo_api(ip)
        probe_geos[ip] = {"address_v4": ip,"city": city, "geometry": {"type": "Point", "coordinates": [lon, lat]}, "id": probes_ids_dict[ip], "is_anchor": False, "country_code": country_code,"asn_v4" : asn_v4}
    print("probes done!")

    print("anchors begin!")
    for ip in anchors_ids_dict.keys():
        lon, lat, city,country_code,asn_v4 = ipinfo_api(ip)
        anchor_geos[ip] = {"address_v4": ip,"city": city, "geometry": {"type": "Point", "coordinates": [lon, lat]}, "id": anchors_ids_dict[ip], "is_anchor": True, "country_code": country_code,"asn_v4" : asn_v4}
    
    print("anchors done!")

    # 写入文件
    with open(f"{DATR_DIR}/generate/user_probes.json", "w") as f:
        json.dump(list(probe_geos.values()), f, indent=4)

    with open(f"{DATR_DIR}/generate/user_anchors.json", "w") as f:
        json.dump(list(anchor_geos.values()), f, indent=4)

    print("Generate anchors.json and probes.json successfully!")

def gen_ping_to_anchors_csv(dataset_raw):
    anchors_ids_dict, probes_ids_dict = gen_id(dataset_raw)
    
    # id添加到 dataset_raw 中
    dataset_raw['anchor_id'] = dataset_raw['anchor_ad'].map(anchors_ids_dict)
    dataset_raw['probe_id'] = dataset_raw['probe_ad'].map(probes_ids_dict)

    # 生成 ping_to_anchors.csv
    ping_data = defaultdict(lambda: defaultdict(list))
    
    for _, row in dataset_raw.iterrows():
        dst = row['anchor_ad']
        src = row['probe_ad']
        prb_id = row['probe_id']
        min_rtt = row['rtt']
        ping_data[src][dst].append((prb_id, min_rtt))
    
    # 转换为DataFrame
    rows = []
    for src, dsts in ping_data.items():
        for dst, prb_rtts in dsts.items():
            for prb_id, min_rtt in prb_rtts:
                rows.append({"src": src, "dst": dst, "prb_id": prb_id, "min_rtt": min_rtt})
    
    ping_df = pd.DataFrame(rows)
    ping_df.to_csv(f"{DATR_DIR}/generate/ping_to_anchors.csv", index=False)
    print("Generate ping_to_anchors.csv successfully!")

if __name__ == "__main__":
    date = "20241213"
    dataset_raw = pd.read_csv(f"{DATR_DIR}/dataset/tmp_ip_anl_geo_ping_{date}.csv",header=None)
    dataset_raw.columns = ['anchor_ad', 'probe_ad', 'rtt', 'ttl', 'region', 'label']

    gen_probes_anchors_json(dataset_raw)
    gen_ping_to_anchors_csv(dataset_raw)
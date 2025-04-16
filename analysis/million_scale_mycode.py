import sys
import os
import requests

from scripts.utils.file_utils import load_json

from scripts.analysis.analysis import *
from default import *


# 逆地理编码
def get_address_from_coordinates(lon, lat):
    proxies = {
    'http': 'http://localhost:7890',
    'https': 'http://localhost:7890',
    }
    # Nominatim API URL
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"

    
    # Headers to respect the usage policy and identify yourself (replace 'your-email@example.com' with your email)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'accept-language':'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
    }
    
    try:
        response = requests.get(url, headers=headers,proxies=proxies)

        data = response.json()
        
        # Extract address from the response
        address = data.get('address', 'Address not found')
        if address == "Address not found":
            return address
        state = address['state']
        return state

    except Exception as e:
        print(f"An error occurred: {e}")
        return None




if __name__ == "__main__":
    # set to True to use your own datasets/measurements
    run_repro = False
    if run_repro:
        # DATASET FILES
        PROBES_FILE = REPRO_PROBES_FILE # 探针列表
        PROBES_AND_ANCHORS_FILE = REPRO_PROBES_AND_ANCHORS_FILE # 探针和锚点列表 max id 7209
        FILTERED_PROBES_FILE = REPRO_FILTERED_PROBES_FILE # 经过过滤的探针列表
        GREEDY_PROBES_FILE = REPRO_GREEDY_PROBES_FILE # 贪婪选择的探针列表
        PAIRWISE_DISTANCE_FILE = REPRO_PAIRWISE_DISTANCE_FILE # 两两之间探测器的距离信息
        VPS_TO_TARGET_TABLE = PROBES_TO_ANCHORS_PING_TABLE # 探针到锚点的ping信息
        VPS_TO_PREFIX_TABLE = PROBES_TO_PREFIX_TABLE # 探针到前缀的映射信息

        # RESULT FILES
        PROBES_TO_ANCHORS_RESULT_FILE = REPRO_PROBES_TO_ANCHORS_RESULT_FILE # 探测器到锚点的测量结果
        ROUND_BASED_ALGORITHM_FILE = REPRO_ROUND_BASED_ALGORITHM_FILE # 基于轮次的算法的结果文件
        ACCURACY_VS_N_VPS_PROBES_FILE = REPRO_ACCURACY_VS_N_VPS_PROBES_FILE # 探测点数量与精度的散点图
        VP_SELECTION_ALGORITHM_PROBES_1_FILE = ( # 使用不同的VP数量,算法结果
            REPRO_VP_SELECTION_ALGORITHM_PROBES_1_FILE
        )
        VP_SELECTION_ALGORITHM_PROBES_3_FILE = (
            REPRO_VP_SELECTION_ALGORITHM_PROBES_3_FILE
        )
        VP_SELECTION_ALGORITHM_PROBES_10_FILE = (
            REPRO_VP_SELECTION_ALGORITHM_PROBES_10_FILE
        )

    else:
        # DATASET FILES
        PROBES_FILE = USER_PROBES_FILE
        PROBES_AND_ANCHORS_FILE = USER_PROBES_AND_ANCHORS_FILE
        FILTERED_PROBES_FILE = USER_FILTERED_PROBES_FILE
        GREEDY_PROBES_FILE = USER_GREEDY_PROBES_FILE
        PAIRWISE_DISTANCE_FILE = USER_PAIRWISE_DISTANCE_FILE
        VPS_TO_TARGET_TABLE = USER_VPS_TO_TARGET_TABLE
        VPS_TO_PREFIX_TABLE = USER_VPS_TO_PREFIX_TABLE

        # RESULT FILES
        PROBES_TO_ANCHORS_RESULT_FILE = USER_PROBES_TO_ANCHORS_RESULT_FILE
        ROUND_BASED_ALGORITHM_FILE = USER_ROUND_BASED_ALGORITHM_FILE
        ACCURACY_VS_N_VPS_PROBES_FILE = USER_ACCURACY_VS_N_VPS_PROBES_FILE
        VP_SELECTION_ALGORITHM_PROBES_1_FILE = USER_VP_SELECTION_ALGORITHM_PROBES_1_FILE
        VP_SELECTION_ALGORITHM_PROBES_3_FILE = USER_VP_SELECTION_ALGORITHM_PROBES_3_FILE
        VP_SELECTION_ALGORITHM_PROBES_10_FILE = (
            USER_VP_SELECTION_ALGORITHM_PROBES_10_FILE
        )

    LIMIT = 1000
    


    import json
    def dump_json(data, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    logger.info("Step 2: Round Algorithm")
    # 基于轮次的方法来优化VP的选择，以提高定位精度。论文中的扩展VP选择算法
    all_probes = load_json(PROBES_AND_ANCHORS_FILE)

    asn_per_vp_ip = {}
    vp_coordinates_per_ip = {}

    for probe in all_probes:
        if (
            "address_v4" in probe
            and "geometry" in probe
            and "coordinates" in probe["geometry"]
        ):
            ip_v4_address = probe["address_v4"]
            if ip_v4_address is None:
                continue
            long, lat = probe["geometry"]["coordinates"]
            asn_v4 = probe["asn_v4"]
            asn_per_vp_ip[ip_v4_address] = asn_v4
            vp_coordinates_per_ip[ip_v4_address] = lat, long

    # clickhouse is required here
    # 获取每对源（src）和目的（dst）节点的最小往返时间（RTT）
    rtt_per_srcs_dst = compute_rtts_per_dst_src_with_csv(
        PROBES_TO_ANCHORS_PING_TABLE, filter, threshold=100
    )
    vp_distance_matrix = load_json(PAIRWISE_DISTANCE_FILE)
 

    probes= load_json(PROBES_FILE)
    error_cdf_per_tier1_vps = {}


    anchors = load_json(USER_ANCHORS_FILE)
    result = []
    for i, (dst, rtt_per_src) in enumerate(sorted(rtt_per_srcs_dst.items())):
        if i % 50 == 0:
            print(f"running with i {i}")
        result_tmp = compute_guessed_and_real_loc(dst, vp_coordinates_per_ip, rtt_per_src)
        dst_guess_loc,dst_real_loc = result_tmp[2],result_tmp[3]
        if dst_guess_loc is None: 
            dst_guess_province = "null"
        elif dst_real_loc is None:
            dst_real_province = "null"
        else:
            dst_guess_province = get_address_from_coordinates(dst_guess_loc[0],dst_guess_loc[1])
            dst_real_province = get_address_from_coordinates(dst_real_loc[0],dst_real_loc[1])

        if isinstance(result_tmp,tuple):
            print(result_tmp)
        else:
            result_tmp.append(dst_guess_province)
            result_tmp.append(dst_real_province)
        result.append(result_tmp)



    dump_json(result, Path("/home/lzj/geoloc-imc-2023/analysis/results/user/user_result_loc.json"))

 
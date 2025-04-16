import sys
import os

from scripts.utils.file_utils import load_json, dump_json

from scripts.analysis.analysis import *
from default import *


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
    
    # 加载过滤后的探针列表
    filtered_probes = load_json(FILTERED_PROBES_FILE)
    
    
    filter = ""
    if len(filtered_probes) > 0:
        # Remove probes that are wrongly geolocated
        # 生成filter条件，在后续数据库查询中过滤错误定位的探针
        in_clause = f"".join([f",toIPv4('{p}')" for p in filtered_probes])[1:]
        filter += f"AND dst not in ({in_clause}) AND src not in ({in_clause}) "

    # 计算误差
    logger.info("Step 1: Compute errors")
    
    # 提取所有探针和锚点
    all_probes = load_json(PROBES_AND_ANCHORS_FILE)
    # compute_geo_info: 从探测器和锚点的数据中计算地理信息，包括VP的坐标、IP映射、国家信息、ASN信息以及VP之间的距离矩阵
    (
        vp_coordinates_per_ip,  # ip: (lat, long)
        ip_per_coordinates,     # (lat, long): ip 与上面互为逆映射
        country_per_vp,         # ip: country 标识每个VP所在的位置所属的国家。
        asn_per_vp,             # ip: asn 标识每个VP所在的ASN。
        vp_distance_matrix,     # (ip1, ip2):dis 存储每对VP之间的地理距离  具体格式?
        probes_per_ip,          # ip: {'location': 'New York', 'asn': 15169},键是IP地址，值是该IP地址作为探测器（probe）时的相关信息或数据
    ) = compute_geo_info(all_probes, PAIRWISE_DISTANCE_FILE)
    

    # 从数据库中获取每对源（src）和目的（dst）节点的最小往返时间（RTT）
    rtt_per_srcs_dst = compute_rtts_per_dst_src( # Compute the guessed geolocation of the targets
        PROBES_TO_ANCHORS_PING_TABLE, filter, threshold=70
    ) # len = 766 筛选了阈值后的数据
    
    # 存储每个目标（destination）可用的虚拟位置（VP）集合
    vps_per_target = {
        dst: set(vp_coordinates_per_ip.keys()) for dst in rtt_per_srcs_dst
    }

    # 计算一些特征，用于绘制精度随着VP数量的散点图,特征包括：
    # 到最近VP的拓扑距离
    # 到最近VP的地理距离    
    features = compute_geolocation_features_per_ip(
        rtt_per_srcs_dst,
        vp_coordinates_per_ip, # ip: (lat, long)
        THRESHOLD_DISTANCES, # [0,40,100,500,1000] # 去除多少km以内的vp
        vps_per_target=vps_per_target, # {dst: set(vps)}
        distance_operator=">",
        max_vps=100000,
        is_use_prefix=False,
        vp_distance_matrix=vp_distance_matrix,
    )

    # analysis/results/reproducibility/cbg_thresholds_probes_to_anchors.json
    dump_json(features, PROBES_TO_ANCHORS_RESULT_FILE)

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
    rtt_per_srcs_dst = compute_rtts_per_dst_src(
        PROBES_TO_ANCHORS_PING_TABLE, filter, threshold=100
    )
    vp_distance_matrix = load_json(PAIRWISE_DISTANCE_FILE)

    TIER1_VPS = [10, 100, 300, 500, 1000]
    greedy_probes = load_json(GREEDY_PROBES_FILE)
    error_cdf_per_tier1_vps = {}
    # 使用VP子集作为第一步，计算CBG
    for tier1_vps in TIER1_VPS:
        print(f"Using {tier1_vps} tier1_vps")
        # 首先是使用贪婪探测的子集，然后在给定的 CBG 区域中取 1 个探测/AS
        error_cdf = round_based_algorithm(  # 格式：dst,error_cdf,len(selected_probes)
            greedy_probes,
            rtt_per_srcs_dst,
            vp_coordinates_per_ip,
            asn_per_vp_ip,
            tier1_vps,
            threshold=40,
        )
        error_cdf_per_tier1_vps[tier1_vps] = error_cdf # 计算每个VP数量对应的精度

    dump_json(error_cdf_per_tier1_vps, ROUND_BASED_ALGORITHM_FILE)

    logger.info("Accuracy vs number of vps probes")
    logger.warning("this step might takes several hours")

    all_probes = load_json(PROBES_AND_ANCHORS_FILE)

    (
        vp_coordinates_per_ip,
        ip_per_coordinates,
        country_per_vp,
        asn_per_vp,
        vp_distance_matrix,
        probe_per_ip,
    ) = compute_geo_info(all_probes, serialized_file=PAIRWISE_DISTANCE_FILE)
            
    logger.info("Accuracy vs number of vps probes")

    subset_sizes = []
    subset_sizes.extend([i for i in range(100, 1000, 100)])
    # subset_sizes.extend([i for i in range(1000, 10001, 1000)])

    rtt_per_srcs_dst = compute_rtts_per_dst_src(
        PROBES_TO_ANCHORS_PING_TABLE, filter, threshold=50
    )

    available_vps = list(vp_coordinates_per_ip.keys())
    accuracy_vs_nb_vps = compute_accuracy_vs_number_of_vps(
        available_vps,
        rtt_per_srcs_dst,
        vp_coordinates_per_ip,
        vp_distance_matrix,
        subset_sizes,
    )

    dump_json(accuracy_vs_nb_vps, ACCURACY_VS_N_VPS_PROBES_FILE)

    logger.info("vp selection algorithm")

    all_probes = load_json(PROBES_AND_ANCHORS_FILE)

    (
        vp_coordinates_per_ip, # 10919 每个ip的经纬度
        ip_per_coordinates, # 10810 每个经纬度对应ip
        country_per_vp, # 每个vp对应国家
        asn_per_vp, # 每个vp对应asn
        vp_distance_matrix, # (ip1, ip2):dis 存储每对VP之间的地理距离
        probes_per_ip, # 每个ip的探针信息
    ) = compute_geo_info(all_probes, PAIRWISE_DISTANCE_FILE)
    # 准备Ping表 定义了用于查找Ping数据的表前缀和主Ping表。
    ping_table_prefix = PROBES_TO_PREFIX_TABLE # ping_table_prefix
    ping_table = PROBES_TO_ANCHORS_PING_TABLE # ping_10k_to_anchors
    N_VPS_SELECTION_ALGORITHM = [1, 3, 10]
    results_files = [
        VP_SELECTION_ALGORITHM_PROBES_1_FILE,
        VP_SELECTION_ALGORITHM_PROBES_3_FILE,
        VP_SELECTION_ALGORITHM_PROBES_10_FILE,
    ]
    # 使用提供的Ping数据表计算每个源到目的地的平均 RTT（Round-Trip Time），过滤掉超出阈值的数据
    rtt_per_srcs_dst_prefix = compute_rtts_per_dst_src(
        ping_table_prefix, filter, threshold=100, is_per_prefix=True # /24前缀到所有其他ip的rtt  763条
    )
    rtt_per_srcs_dst = compute_rtts_per_dst_src(ping_table, filter, threshold=70) # ip地址到所有其他ip的rtt   # 766条

    for i, n_vp in enumerate(N_VPS_SELECTION_ALGORITHM):
        # 计算每个目的前缀的最短RTT（Round Trip Time）探测点。
        vps_per_target = compute_closest_rtt_probes( # 得到每个目标对应的VP点。(最小RTT)
            rtt_per_srcs_dst_prefix,
            vp_coordinates_per_ip,
            vp_distance_matrix,
            n_shortest=n_vp,
            is_prefix=True,
        )

        # 计算得到特征散点图
        features = compute_geolocation_features_per_ip(
            rtt_per_srcs_dst,
            vp_coordinates_per_ip,
            [0],
            vps_per_target=vps_per_target,
            distance_operator=">",
            max_vps=100000,
            is_use_prefix=True,
            vp_distance_matrix=vp_distance_matrix,
            is_multiprocess=True,
        )

        ofile = results_files[i]
        dump_json(features, ofile)

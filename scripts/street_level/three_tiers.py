# One function per tier of the street level method.

import time

from scripts.analysis.analysis import local_circle_preprocessing
from scripts.street_level.landmark import get_all_landmarks_and_stats_from_points
from scripts.utils.helpers import get_center_of_poly, get_points_in_poly
from scripts.street_level.traceroutes_results import (
    get_circles_to_target,
    start_and_get_traceroutes,
)


def tier_1(target_ip, res, vps=None):
    st = time.time()
    # Get all circles (from each VP to the target)  得到所有VP到目标之间的圆
    all_circles = get_circles_to_target(target_ip, vps)

    # Try the recommended internet speed at first 
    speed_threshold = 4 / 9
    imp_circles = local_circle_preprocessing(
        all_circles, speed_threshold=speed_threshold
    )
    lat, lon = get_center_of_poly(imp_circles, speed_threshold) # 计算这些圆的中心点

    # If there is no intersection polygone try a slower interent speed
    if lat == None or lon == None:
        speed_threshold = 2 / 3
        imp_circles = local_circle_preprocessing(
            all_circles, speed_threshold=speed_threshold
        )
        lat, lon = get_center_of_poly(imp_circles, speed_threshold)
    res["speed_threshold"] = speed_threshold
    res["tier1:lat"] = lat
    res["tier1:lon"] = lon
    res["vps"] = imp_circles
    et = time.time()
    # Saving the time needed to perform this step 
    res["tier1:duration"] = et - st
    return res


def tier_2(target_ip, res, vps=None):
    st = time.time()
    tier2_points = get_points_in_poly(res["vps"], 36, 5, res["speed_threshold"])
    res["tier2:all_points_count"] = len(tier2_points)

    # We remove points further than 1000km from the estimated center of the polygone (in case the intersection area is too big)
    # 我们移除距离中心点大于1000km的点
    tier2_points = tier2_points[: 200 * 10 + 1]
    res["tier2:inspected_points_count"] = len(tier2_points)
    # 如果没有有效的点则设置为空返回
    if len(tier2_points) == 0:
        res["tier2:lat"] = None
        res["tier2:lon"] = None
        et = time.time()
        res["tier2:duration"] = et - st
        return res

    (
        failed_dns_count,
        failed_asn_count,
        cdn_count,
        failed_header_test_count,
        landmarks,
    ) = get_all_landmarks_and_stats_from_points(tier2_points) # 得到地标网站，并记录各种结果
    
    # We save stats for possiblity of a website to be used as a landmark
    res["tier2:failed_dns_count"] = failed_dns_count
    res["tier2:failed_asn_count"] = failed_asn_count
    res["tier2:cdn_count"] = cdn_count
    res["tier2:non_cdn_count"] = len(landmarks) + failed_header_test_count
    res["tier2:landmark_count"] = len(landmarks)
    res["tier2:failed_header_test_count"] = failed_header_test_count
    res["tier2:landmarks"] = landmarks
 
    # 没有地标则直接返回
    if len(res["tier2:landmarks"]) == 0:
        res["tier2:lat"] = None
        res["tier2:lon"] = None
        et = time.time()
        res["tier2:duration"] = et - st
        return res

    # 启动跟踪路由
    res["tier2:traceroutes"] = start_and_get_traceroutes(
        target_ip, res["vps"], res["tier2:landmarks"], vps
    )
    all_circles = []
    best_rtt = 5000
    res_lat = None
    res_lon = None
    # 遍历追踪路由结果，筛选有效RTT值并计算最小RTT对应的经纬度
    for probe_ip, target_ip, landmark_ip, r1ip, rtt, lat, lon, traceroute_id in res[
        "tier2:traceroutes"
    ]:
        if rtt < 0:
            continue
        all_circles.append((lat, lon, rtt, None, None))
        if rtt < best_rtt:
            best_rtt = rtt
            res_lat = lat
            res_lon = lon

    # If there is no valid RTT then tier 2 has failed and we can not go further
    # 若无有效RTT，则设置结果为空；
    if len(all_circles) == 0:
        res["tier2:lat"] = None
        res["tier2:lon"] = None
        et = time.time()
        res["tier2:duration"] = et - st
        return res

    # If not, we use the smallest rtt landmark as
    # 否则保存最小RTT对应的经纬度及所有圆信息
    res["tier2:lat"] = res_lat
    res["tier2:lon"] = res_lon
    res["tier2:final_circles"] = all_circles
    et = time.time()
    res["tier2:duration"] = et - st
    return res


def tier_3(target_ip, res, vps=None):
    st = time.time()
    # tier失败则不能继续
    if "tier2:final_circles" not in res:
        res["tier3:lat"] = None
        res["tier3:lon"] = None
        et = time.time()
        res["tier3:duration"] = et - st
        return res

    else:
        all_circles = res["tier2:final_circles"]

    imp_circles = local_circle_preprocessing(
        all_circles, speed_threshold=res["speed_threshold"]
    )
    #获取多边形内的点
    tier3_points = get_points_in_poly(
        imp_circles, 10, 1, res["speed_threshold"], res["vps"]
    )
    res["tier3:all_points_count"] = len(tier3_points)

    # We remove points/zipcodes further then 40Km away from the center of the polygone
    # 去掉距离中心超过 40 公里的点：
    tier3_points = tier3_points[: 40 * 36 + 1]
    res["tier3:inspected_points_count"] = len(tier3_points)
    if len(tier3_points) == 0:
        res["tier3:lat"] = None
        res["tier3:lon"] = None
        et = time.time()
        res["tier3:duration"] = et - st
        return res

    (
        failed_dns_count,
        failed_asn_count,
        cdn_count,
        failed_header_test_count,
        tmp_landmarks,
    ) = get_all_landmarks_and_stats_from_points(tier3_points) # 获取地标及其统计信息：
    landmarks = []
    
    # 过滤地标,只要tier3中新发现的地标
    for landmark in tmp_landmarks:
        ip = landmark[0]
        found = False
        for t2_lm in res["tier2:landmarks"]:
            if t2_lm[0] == ip:
                found = True
                break
        if not found:
            landmarks.append(landmark)

    res["tier3:failed_dns_count"] = failed_dns_count
    res["tier3:failed_asn_count"] = failed_asn_count
    res["tier3:cdn_count"] = cdn_count
    res["tier3:non_cdn_count"] = len(landmarks) + failed_header_test_count
    res["tier3:landmark_count"] = len(landmarks)
    res["tier3:failed_header_test_count"] = failed_header_test_count
    res["tier3:landmarks"] = landmarks
    # 检查是否有有效的地标：
    if len(res["tier3:landmarks"]) == 0:
        res["tier3:lat"] = None
        res["tier3:lon"] = None
        et = time.time()
        res["tier3:duration"] = et - st
        return res
    # 启动跟踪路由
    res["tier3:traceroutes"] = start_and_get_traceroutes(
        target_ip, res["vps"], res["tier3:landmarks"], vps
    )
    # 查找最佳 RTT 对应的经纬度
    best_lon = None
    best_lat = None
    best_rtt = 5000
    for probe_ip, target_ip, landmark_ip, r1ip, rtt, lat, lon, traceroute_id in res[
        "tier2:traceroutes"
    ]:
        if rtt < 0:
            continue
        if rtt < best_rtt:
            best_rtt = rtt
            best_lon = lon
            best_lat = lat
    for probe_ip, target_ip, landmark_ip, r1ip, rtt, lat, lon, traceroute_id in res[
        "tier3:traceroutes"
    ]:
        if rtt < 0:
            continue
        if rtt < best_rtt:
            best_rtt = rtt
            best_lon = lon
            best_lat = lat

    res["tier3:lat"] = best_lat
    res["tier3:lon"] = best_lon
    et = time.time()
    res["tier3:duration"] = et - st
    return res


def get_all_info_geoloc(target_ip, vps=None):
    # Init results
    res = {
        "target_ip": target_ip,
        "tier1:done": False,
        "tier2:done": False,
        "tier3:done": False,
        "negative_rtt_included": True,
    }
    res = tier_1(target_ip, res, vps=vps)

    # Using tier 1(CBG) results as geolocation if the other steps fail
    # 其他步骤失败，使用tier 1的结果作为定位结果
    res["lat"] = res["tier1:lat"]
    res["lon"] = res["tier1:lon"]
    if res["tier1:lat"] == None or res["tier1:lon"] == None:
        return res
    res["tier1:done"] = True

    res = tier_2(target_ip, res, vps=vps)

    # Using tier 2 resultsas geolocation if the last step fails
    if res["tier2:lat"] == None or res["tier2:lon"] == None:
        return res
    else:
        res["tier2:done"] = True
        res["lat"] = res["tier2:lat"]
        res["lon"] = res["tier2:lon"]

    res = tier_3(target_ip, res, vps=vps)

    if res["tier3:lat"] != None and res["tier3:lon"] != None:
        res["tier3:done"] = True
        res["lat"] = res["tier3:lat"]
        res["lon"] = res["tier3:lon"]

    return res


def geoloc(target_ip):
    """
    This function return a dict containint the lat, lon coordinates of the given target_ip.
    The target_ip should be traceroutable.
    The function gives a less informative gelocation result than get_all_info_geoloc
    """
    all_info = get_all_info_geoloc(target_ip)
    return {"lat": all_info["lat"], "lon": all_info["lon"]}

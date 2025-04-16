## 数据集初始化
./datasets/create_datasets.ipynb

使用repo数据可以不使用这个步骤

RIPE Atlas 锚点anchor集的地理位置比 RIPE Atlas 探针probes更准确,因此数量更少

## Millon paper复现

./analysis/million_scale.py
包括：
本文件从数据库(已有的表)中提取probes和anchors之间的RTT，不需要重新计算RTT。
Step 1: Compute errors
地理定位精度分析预处理，从数据集中计算各个探测器相对于已知坐标的误差。

Step 2: Round Algorithm
扩展的VP选择算法，以及他的验证。对应论文图3b

3.Accuracy vs number of vps probes
计算误差与探测点数量之间的关系。

4.vp selection algorithm
原文VP选择算法实现(最短ping)

./measurements/million_scale_measurements.py

执行从VP到target的ping测量


./analysis/plot.ipynb
绘制论文图表

## street level paper

仓库md：不需要额外的步骤来复现街道级实验。

但无法运行plot中的street部分脚本。

./measurements/landmark_traceroutes.ipynb
进行后面的街道级定位操作，缺少altas api

./scripts/street_level/three_tiers.py 
完整实现了street level 的三层定位系统.

./scripts/street_level/traceroutes_results.py
工具函数


# 使用实际数据进行GeoPing

1. 给定tmp_ip_anl_geo_ping_20241213.csv 数据放入 geoloc-imc-2023/Geo_mycode/data/dataset 文件夹下
2. 执行geoloc-imc-2023/Geo_mycode/scripts/gen_dataset.py 生成user数据集，生成文件包括 ping_to_anchors.csv(探测点到被探测点延迟信息), user_anchors.csv(被探测点信息),user_probes.csv(探针信息)
3. 执行geoloc-imc-2023/datasets/create_datasets_mycode.ipynb 生成项目运行需要的数据集，生成数据在 lzj/geoloc-imc-2023/datasets/user_datasets下
4. 执行geoloc-imc-2023/analysis/million_scale_mycode.py 进行Geoping模拟，未使用优化算法(VP数量和信息不足，详见(https://alidocs.dingtalk.com/i/nodes/EpGBa2Lm8aZxe5myCQzB29EOWgN7R35y?utm_scene=person_space))。
5. 执行geoloc-imc-2023/analysis/eva_result_mycode.ipynb 进行结果分析。


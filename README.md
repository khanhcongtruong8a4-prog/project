# Active research development

Use [panda_research/README.md](panda_research/README.md) for the combined Gaz-model
development package, API fixes, Pinocchio/MuJoCo checks and research protocol.
The earlier PyBullet grasp demo below is a separate introductory example.

Current work: **P1 independent-review remediation / v1.2.2 r2 DRAFT**.
Download the [clean cumulative review overlay](downloads/IC2AI_Panda_P1_Review_Remediation_v1.2.2_DRAFT_2026-11-02_r2.zip)
and its [SHA-256](downloads/IC2AI_Panda_P1_Review_Remediation_v1.2.2_DRAFT_2026-11-02_r2.zip.sha256).
Apply it to the unchanged accepted Action 3 r2 package using the included instructions.
Read the [reviewer issue response](panda_research/reports/p1_v1.2.2_r2/REVIEW_REMEDIATION.md)
and [A2 entry checklist](panda_research/reports/p1_v1.2.2_r2/A2_ENTRY_CHECKLIST.md).

The frozen development hold fails the 0.02 rad/s speed tolerance at joints 3
and 7 after 1.25 ms in every C4 cell. Signed-clock support and actual abort-state
QP checks are now implemented. No valid zero-time endpoint is available.
**A1 GO; frozen P1 FAIL / startup NOT APPROVED; official A2/A3/Level 1/publication NO-GO.**
No gain/disturbance/model retuning or official A2 run is included.

# Mô phỏng Franka Emika Panda

Python 3.12 và PyBullet, dùng mô hình Panda và khối hộp có sẵn trong `pybullet_data`.
Không cần robot thật, ROS hay tải thêm mô hình.

## Cài đặt

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Nếu Python 3.12 cần biên dịch PyBullet từ mã nguồn, máy cần GCC/G++.
Có thể chọn bộ biên dịch bằng `CC=gcc CXX=g++` trước lệnh cài bằng pip.
Trong môi trường cloud đã chuẩn bị, dùng `/workspace/panda-venv/bin/python`
thay cho `.venv/bin/python`, từ thư mục `/workspace/project`.

## Chạy

```bash
# Chạy trên cloud, không cần màn hình; báo lỗi nếu gắp không thành công
.venv/bin/python simulation.py

# Máy tính có desktop: xem robot tự gắp và nâng khối hộp
.venv/bin/python simulation.py --gui

# Điều khiển vị trí bàn kẹp và độ mở ngón bằng thanh trượt
.venv/bin/python simulation.py --gui --manual
```

Demo dùng động học nghịch để điều khiển 7 khớp cánh tay; hai ngón kẹp giữ vật
bằng tiếp xúc và ma sát. Không gắn vật vào robot bằng constraint.
Trong chế độ thủ công, mục tiêu ngoài tầm với có thể không đạt được.
Đóng bằng Ctrl+C. GUI cần màn hình đồ họa; môi trường cloud dùng chế độ mặc định.
Đây là ví dụ mô phỏng, chưa dùng để điều khiển robot thật.

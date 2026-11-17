# MergeSort CUTOFF Experiment

> **Thí nghiệm tìm CUTOFF tối ưu cho Mergesort** - Bài tập môn Cấu trúc dữ liệu và Giải thuật, Trường Đại học Công nghệ - ĐHQGHN.

Mergesort (theo bài giảng) chuyển sang insertion sort khi đoạn con có độ dài không quá **CUTOFF**. Giáo trình dùng **CUTOFF** 7 hoặc 10. Repo này chứa code, cấu hình và script để đo thời gian sắp xếp bằng **JMH** với CUTOFF từ 0 đến 512, rồi tìm giá trị tốt nhất trên một máy cụ thể.

---

## 📎 Tài liệu

| Tài liệu | Link |
|:---|:---|
| **Báo cáo thí nghiệm** | [Báo cáo](https://drive.google.com/file/d/1S_jDUNdvmhY5xuvuO0HyyFLMozWL77IV/view?usp=sharing) |

---

## Mô tả Bài toán

- **Câu hỏi:** với Mergesort có CUTOFF, giá trị CUTOFF nào cho thời gian sắp xếp nhỏ nhất trên máy thực nghiệm, và các giá trị 7, 10 của giáo trình chậm hơn bao nhiêu?
- **Biến độc lập:** CUTOFF (0–512), kích thước mảng N (10⁴, 10⁵, 10⁶), loại dữ liệu.
- **Biến đo:** thời gian sắp xếp một mảng `Integer[]` (JMH, chế độ `SingleShotTime`, 5 JVM mỗi cấu hình).
- **Phân tích:** khoảng tin cậy 95% trên log tỉ số thời gian, kiểm nghiệm lại theo seed, vùng tốt ±2%, doubling test và đếm thao tác.

### Kết quả chính

Trên máy thực nghiệm (AMD Ryzen 5 7235HS, RAM 12 GB một kênh, Windows 11, JDK 25):

| CUTOFF | Chậm hơn CUTOFF tốt nhất | Khoảng tin cậy 95% |
|:---:|:---:|:---:|
| **≈ 25** | tốt nhất | — |
| 20 – 48 | ≤ 2% | — |
| 10 | 4,9% | 2,9 – 7,0% |
| 7 | 7,3% | 5,6 – 9,1% |

---

## Công nghệ & Môi trường

### Các công nghệ sử dụng

| Tầng | Công nghệ | Mục đích |
|:---|:---|:---|
| **Thuật toán** | Java | Mergesort có CUTOFF, đếm thao tác |
| **Đo đạc** | JMH 1.37 | Benchmark thời gian sắp xếp, chép mảng, benchmark chỉ dùng CPU |
| **Kiểm thử** | JUnit 5 | Kiểm tra tính đúng của `MergeSort` |
| **Build** | Apache Maven | Biên dịch, đóng gói `benchmarks.jar` |
| **Điều phối** | Python | Sinh dữ liệu, chạy các đợt đo theo file cấu hình |
| **Phân tích** | NumPy, pandas, SciPy, Matplotlib | Thống kê, bootstrap, vẽ hình |

### Yêu cầu Cài đặt

| Phần mềm | Phiên bản tối thiểu | Ghi chú |
|:---|:---|:---|
| **JDK** | 17 | Thí nghiệm dùng JDK 25 |
| **Maven** | 3.9 | |
| **Python** | 3.11 | Cài gói bằng `py -3 -m pip install -r requirements.txt` |

---

## Cấu trúc Dự án

```
MergeSort-CUTOFF_Experiment/
│
├── src/
│   ├── main/java/cutoff/
│   │   ├── sort/MergeSort.java          # Mergesort có CUTOFF
│   │   ├── data/DatasetIO.java          # Đọc dữ liệu .bin
│   │   └── count/OperationCount.java    # Đếm thao tác (đợt 3)
│   ├── jmh/java/cutoff/bench/           # Benchmark JMH: sắp xếp, chép mảng, chỉ dùng CPU
│   └── test/java/cutoff/sort/           # Test tính đúng của MergeSort
│
├── scripts/
│   ├── gen_data.py                      # Sinh 58 mảng dữ liệu từ seed cố định
│   ├── run_experiment.py                # Chạy một đợt đo theo file cấu hình
│   ├── sysinfo.py                       # Ghi lại cấu hình máy
│   ├── analyze_cutoff.py                # CUTOFF tốt nhất, khoảng tin cậy, bootstrap, doubling test, vẽ hình
│   └── noise_check.py                   # Kiểm tra nguồn gốc nhiễu đo
│
├── configs/                             # Cấu hình các đợt đo (pilot, e1, e1x, e2, e4)
├── data/manifest.csv                    # SHA-256 của từng file dữ liệu
├── requirements.txt                     # Gói Python
├── pom.xml
└── README.md
```

---

## Vị trí file JAR

Sau khi build, file **executable JAR** chứa toàn bộ benchmark được tạo tại:

| File | Vai trò |
|:---|:---|
| `target/benchmarks.jar` | Chạy benchmark JMH và chương trình đếm thao tác |

> **Lưu ý:** Sau mỗi lần sửa mã Java cần build lại; runner từ chối đo nếu `benchmarks.jar` cũ hơn mã nguồn.

---

## Hướng dẫn Tái lập Thí nghiệm

### Bước 1: Tải mã nguồn
```bash
git clone https://github.com/Reece1512/MergeSort-CUTOFF_Experiment.git
cd MergeSort-CUTOFF_Experiment
py -3 -m pip install -r requirements.txt
```

### Bước 2: Build và kiểm thử
```bash
mvn package
```

### Bước 3: Sinh dữ liệu
File `.bin` (khoảng 87 MB) không nằm trong repo. Sinh lại từ seed cố định và đối chiếu với SHA-256 trong `data/manifest.csv`:
```bash
py -3 scripts/gen_data.py
py -3 scripts/gen_data.py --verify
```
Gồm: random, duplicates (16 giá trị), nearly_sorted (1% phần tử bị đổi chỗ) với 5 seed, và ascending, descending, ở N = 10⁴, 10⁵, 10⁶; thêm dữ liệu random cho doubling test từ N = 15 625 tới 2 000 000.

### Bước 4: Chạy đo
Trước khi đo: cắm sạc, chọn chế độ hiệu năng cao nhất, đóng các ứng dụng khác và không dùng máy trong lúc đo. Thêm `--dry-run` để xem số cấu hình và ước lượng thời gian. Bị gián đoạn thì chạy lại đúng lệnh để tiếp tục.

```bash
py -3 scripts/run_experiment.py configs/<tên đợt>.toml
```

### Bước 5: Phân tích
```bash
py -3 scripts/analyze_cutoff.py pilot
py -3 scripts/analyze_cutoff.py grid --campaign e1
py -3 scripts/analyze_cutoff.py grid --campaign e1,e1x
py -3 scripts/analyze_cutoff.py grid --campaign e2
py -3 scripts/analyze_cutoff.py doubling
```
Mỗi lệnh ghi bảng CSV và `summary.md` vào `results/analysis_<đợt>/`, hình vào `report/figures/`.

---

## Danh sách Thí nghiệm

| Đợt | Nội dung | File cấu hình | Thời gian |
|:--:|:---|:---|:--:|
| **Pilot** | Chọn GC và số vòng chạy nháp | `configs/pilot.toml` | ~5 phút |
| **1** | Dữ liệu ngẫu nhiên, CUTOFF 0–64 | `configs/e1.toml` | ~60 phút |
| **1x** | Dữ liệu ngẫu nhiên, CUTOFF 40–512 | `configs/e1x.toml` | ~15 phút |
| **2** | Các loại dữ liệu khác, CUTOFF 0–64 | `configs/e2.toml` | ~20 phút |
| **3** | Đếm thao tác (không phụ thuộc máy) | `java -cp target/benchmarks.jar cutoff.count.OperationCount results/e3/operations.csv` | ~5 phút |
| **4** | Doubling test | `configs/e4.toml` | ~15 phút |
| **Nhiễu** | So nhiễu của benchmark sắp xếp với benchmark chỉ dùng CPU (tùy chọn) | `py -3 scripts/noise_check.py` | |

### Quy tắc Phân tích

| Nội dung | Cách làm |
|:---|:---|
| **Đơn vị quan sát** | Mỗi mảng (mỗi seed); thời gian ở một CUTOFF là trung bình của các JVM |
| **CUTOFF tốt nhất** | Chia thời gian mỗi mảng cho mức chung của nó, lấy trung bình nhân trên các mảng, chọn giá trị nhỏ nhất |
| **So sánh hai CUTOFF** | Khoảng tin cậy 95% theo phân phối t trên log tỉ số thời gian từng mảng |
| **Vùng tốt** | Các CUTOFF chậm hơn CUTOFF tốt nhất không quá 2% |
| **Bootstrap** | Lấy mẫu lại các seed 2000 lần để xem CUTOFF tốt nhất có ổn định không |
| **Đối chứng** | CUTOFF 0 và 1 chia mảng giống hệt nhau, nên tỉ số thời gian lý tưởng là 1 |
| **Gộp cấu hình** | Các CUTOFF cho cùng cách chia mảng chỉ đo một lần và dùng chung kết quả |

> **Lưu ý khi tái lập:** Thời gian tuyệt đối sẽ khác trên máy khác. CUTOFF tối ưu phụ thuộc vào CPU, bộ nhớ đệm, JVM và loại dữ liệu, nên có thể lệch khỏi 25. Dạng chữ U của đường cong và việc CUTOFF 0 chậm nhất được kỳ vọng là lặp lại.

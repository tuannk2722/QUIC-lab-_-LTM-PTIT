# T03 — Triển khai và hiệu năng của giao thức QUIC

> **Môn:** Lập trình mạng  
> **Topic:** T03 — QUIC Protocol Implementation và Performance  
> **Trọng tâm:** QUIC transport protocol, multiplexing, 0-RTT, Head-of-Line Blocking, reliability, flow control, congestion control, connection migration và benchmark QUIC vs TCP.

---

## 1. QUIC thực sự là gì?

Cách dễ hiểu nhất là nhìn vào stack mạng.

Một kết nối HTTPS kiểu truyền thống thường có dạng:

```text
Application
    │
   HTTP
    │
 TLS 1.3
    │
   TCP
    │
    IP
```

Trong khi một ứng dụng chạy trực tiếp trên QUIC sẽ gần giống:

```text
Application
    │
    QUIC
 ┌───────────────┐
 │ Streams       │
 │ Reliability   │
 │ Flow Control  │
 │ Congestion    │
 │ TLS 1.3       │
 └───────────────┘
    │
   UDP
    │
    IP
```

Điểm đầu tiên cần hiểu thật chắc:

> **QUIC chạy trên UDP, nhưng QUIC không phải là “UDP không đảm bảo”.**

UDP ở đây chủ yếu đóng vai trò phương tiện để đưa các datagram từ máy này sang máy kia. Phía trên UDP, QUIC tự xây dựng rất nhiều chức năng mà TCP vốn cung cấp như:

- Reliability.
- ACK và loss detection.
- Retransmission dữ liệu cần thiết.
- Flow control.
- Congestion control.

Đồng thời QUIC còn bổ sung các khả năng quan trọng như:

- Multiple independent streams.
- TLS 1.3 tích hợp trực tiếp vào transport.
- 1-RTT/0-RTT connection establishment.
- Connection ID và connection migration.

Có thể hình dung đơn giản:

```text
UDP nói:
"Tôi chỉ chuyển datagram này đi.
 Có tới nơi hay không thì không phải việc của tôi."

QUIC nói:
"Được, vậy tôi sẽ tự:
 - đánh số packet
 - kiểm tra ACK
 - phát hiện packet loss
 - gửi lại dữ liệu cần thiết
 - điều khiển tốc độ gửi
 - mã hóa
 - chia dữ liệu thành nhiều stream."
```

Vì vậy, nói **“QUIC nhanh vì dùng UDP”** là không chính xác.

UDP không tự làm QUIC nhanh. QUIC nhanh hơn trong một số điều kiện vì kiến trúc của nó cho phép giải quyết những hạn chế quan trọng của TCP, đặc biệt là:

- giảm thời gian thiết lập kết nối;
- multiplexing nhiều stream độc lập;
- tránh Head-of-Line Blocking giữa các stream;
- hỗ trợ connection migration tốt hơn.

---

## 2. QUIC đang cố giải quyết những vấn đề gì của TCP?

Muốn hiểu QUIC, cần nhìn từ những giới hạn của TCP trong các ứng dụng mạng hiện đại.

### 2.1. TCP + TLS cần nhiều bước thiết lập kết nối

Trước tiên cần hiểu **RTT — Round Trip Time**.

Giả sử:

```text
Client --------------> Server
       50 ms

Client <-------------- Server
       50 ms
```

Một vòng đi và về mất:

```text
RTT = 100 ms
```

TCP trước khi truyền dữ liệu phải thiết lập connection bằng 3-way handshake:

```text
Client                     Server

SYN ---------------------->

    <---------------- SYN + ACK

ACK ---------------------->
```

Nếu ứng dụng cần mã hóa TLS thì sau TCP handshake còn có TLS handshake.

Một cách đơn giản để hình dung TCP + TLS 1.3:

```text
Client                         Server

        TCP handshake
SYN --------------------------->
    <----------------------- SYN ACK
ACK --------------------------->

        TLS handshake
ClientHello ------------------->
    <---- ServerHello, Finished

Application Data ------------->
```

Điều đó có nghĩa là trước khi application thực sự trao đổi dữ liệu hữu ích, client và server phải trải qua nhiều bước trao đổi trên mạng.

QUIC thiết kế khác.

TLS 1.3 được **tích hợp trực tiếp vào quá trình thiết lập QUIC connection**, thay vì:

```text
TCP xong
↓
mới TLS
```

Có thể hình dung:

```text
Client                                  Server

QUIC Initial
+ TLS ClientHello ---------------------->

                        QUIC Handshake
                  <----- TLS response

Application Data ----------------------->
```

Transport handshake và security handshake được kết hợp chặt chẽ hơn.

Với một full handshake bình thường, QUIC có thể đạt trạng thái gửi application data bảo mật sau khoảng **1 RTT**.

---

### 2.2. TCP nhìn dữ liệu như một ordered byte stream duy nhất

Đây là một trong những điểm quan trọng nhất của topic T03.

TCP cung cấp:

> **Reliable ordered byte stream.**

Ví dụ application gửi:

```text
ABCDEFGHIJKLMN
```

TCP đảm bảo application phía nhận thấy dữ liệu theo đúng thứ tự:

```text
ABCDEFGHIJKLMN
```

Giả sử dữ liệu được chia thành các segment/packet logic như:

```text
Packet 1: ABC
Packet 2: DEF
Packet 3: GHI
Packet 4: JKL
```

Nếu packet chứa `DEF` bị mất:

```text
Packet 1: ABC    ✓
Packet 2: DEF    X mất
Packet 3: GHI    ✓
Packet 4: JKL    ✓
```

Receiver ở tầng mạng có thể đã nhận dữ liệu phía sau, nhưng application đang đọc một **ordered TCP byte stream** nên không thể bỏ qua khoảng trống đó.

Nó phải chờ phần `DEF` được phục hồi.

Sau khi dữ liệu bị mất được retransmit:

```text
ABC + DEF + GHI + JKL
```

application mới có thể tiếp tục nhận dữ liệu theo đúng thứ tự.

Đây là một dạng:

> **Head-of-Line Blocking (HOL blocking).**

---

### 2.3. Vấn đề nghiêm trọng hơn khi multiplex nhiều luồng logic trên một TCP connection

Giả sử application có ba luồng dữ liệu độc lập:

```text
Stream A = hình ảnh
Stream B = CSS
Stream C = JavaScript
```

Nếu multiplex chúng trên **một TCP connection**, dữ liệu về bản chất cuối cùng vẫn đi vào một ordered byte stream của TCP:

```text
TCP byte stream

A1 B1 C1 A2 B2 C2 A3 B3 C3 ...
```

Giả sử phần chứa `A2` bị mất:

```text
A1 B1 C1 [A2 mất] B2 C2 A3 B3 C3
```

TCP không biết A, B và C là ba luồng application độc lập.

Đối với TCP, tất cả chỉ là:

```text
byte 1
byte 2
byte 3
...
```

Vì vậy khoảng trống ở byte stream có thể khiến dữ liệu phía sau chưa được giao lên application dù một phần trong số đó thuộc các luồng logic khác.

Kết quả có thể được hình dung:

```text
A bị block   ← hợp lý vì dữ liệu của A bị mất
B bị block   ← không cần thiết ở góc nhìn application
C bị block   ← không cần thiết ở góc nhìn application
```

Đây chính là vấn đề mà multiplexing của QUIC nhắm tới.

---

## 3. QUIC sử dụng nhiều stream độc lập

Một QUIC connection có thể chứa rất nhiều stream:

```text
                QUIC CONNECTION
                      │
          ┌───────────┼───────────┐
          │           │           │
       Stream 0    Stream 4    Stream 8
          │           │           │
        data A      data B      data C
```

Mỗi QUIC stream là một **ordered byte sequence riêng**.

Ví dụ:

```text
Stream A:
A1 A2 A3 A4

Stream B:
B1 B2 B3 B4

Stream C:
C1 C2 C3 C4
```

Nếu dữ liệu `A2` bị mất:

```text
Stream A:
A1 [waiting A2] A3 A4
       BLOCKED

Stream B:
B1 B2 B3 B4
       ↓
application nhận bình thường

Stream C:
C1 C2 C3 C4
       ↓
application nhận bình thường
```

Đây là ý nghĩa chính xác của việc QUIC tránh:

> **Head-of-Line Blocking giữa các stream độc lập.**

Tuy nhiên cần tránh một phát biểu sai phổ biến:

> ❌ “QUIC loại bỏ hoàn toàn Head-of-Line Blocking.”

Không đúng.

Cách nói chính xác hơn là:

> **QUIC tránh transport-level Head-of-Line Blocking giữa các stream độc lập.**

Trong **cùng một stream**, dữ liệu vẫn ordered.

Ví dụ:

```text
Stream A:
A1 → A2 → A3 → A4
```

Nếu A2 bị mất thì A3 vẫn phải chờ A2 nếu application đang đọc stream theo thứ tự.

Ngoài ra, các stream trong cùng một QUIC connection vẫn có thể chia sẻ cùng một network path và cùng congestion controller. Vì vậy packet loss vẫn có thể làm congestion window giảm và làm toàn connection gửi chậm hơn.

QUIC không làm packet loss biến mất.

Điểm khác biệt là:

```text
mất dữ liệu của Stream A
```

không bắt buộc:

```text
Stream B + Stream C
```

phải chờ khoảng trống dữ liệu của Stream A.

---

## 4. Connection → Stream → Frame → Packet

Đây là bốn khái niệm rất dễ bị nhầm lẫn.

Giả sử ta có:

```text
QUIC Connection
│
├── Stream A
├── Stream B
└── Stream C
```

Dữ liệu stream được đóng thành **STREAM frame**.

Ví dụ:

```text
STREAM frame
┌────────────────────────┐
│ Stream ID = 4          │
│ Offset = 1000          │
│ Length = 500           │
│ Data = ............... │
└────────────────────────┘
```

Một QUIC packet có thể chứa nhiều frame:

```text
QUIC Packet
┌─────────────────────────┐
│ QUIC Header             │
├─────────────────────────┤
│ STREAM frame (Stream A) │
├─────────────────────────┤
│ STREAM frame (Stream B) │
├─────────────────────────┤
│ ACK frame               │
└─────────────────────────┘
```

Có thể nhớ theo mental model:

```text
Connection
   ↓
Streams
   ↓
Frames
   ↓
Packets
   ↓
UDP datagrams
   ↓
IP packets
```

Một số QUIC frame type quan trọng:

| Frame | Công dụng |
|---|---|
| `STREAM` | Mang application data của một stream |
| `ACK` | Xác nhận packet đã nhận |
| `CRYPTO` | Mang dữ liệu TLS handshake |
| `PING` | Kiểm tra/duy trì hoạt động |
| `MAX_DATA` | Tăng connection-level flow-control limit |
| `MAX_STREAM_DATA` | Tăng flow-control limit của một stream |
| `MAX_STREAMS` | Cho phép peer mở thêm stream |
| `PATH_CHALLENGE` | Kiểm tra một network path mới |
| `PATH_RESPONSE` | Phản hồi path validation |
| `NEW_CONNECTION_ID` | Cấp Connection ID mới |
| `CONNECTION_CLOSE` | Đóng connection |

Không cần đưa toàn bộ bảng này lên slide, nhưng cần hiểu chúng tồn tại để thấy rằng:

> QUIC không đơn giản chỉ là “TCP viết lại trên UDP”.

Nó là một transport protocol có mô hình packet/frame riêng.

---

## 5. Reliability của QUIC hoạt động thế nào?

Một câu hỏi rất dễ xuất hiện khi Q&A là:

> “UDP không reliable, vậy tại sao QUIC lại reliable?”

Giả sử sender gửi:

```text
Packet #10
Packet #11
Packet #12
Packet #13
```

Receiver nhận:

```text
#10 ✓
#11 ✓
#12 X
#13 ✓
```

Receiver gửi ACK thể hiện những packet mà nó đã nhận.

Sender sau đó có thể suy luận:

```text
Packet #12 có khả năng đã bị mất.
```

QUIC sử dụng các cơ chế như:

- ACK.
- RTT estimation.
- Packet threshold.
- Time threshold.
- Probe Timeout (PTO).

để phát hiện packet loss.

Một chi tiết rất quan trọng:

> **QUIC không retransmit nguyên packet cũ với cùng packet number.**

Ví dụ packet #12 chứa:

```text
Packet #12
┌───────────────────┐
│ Stream A data     │
│ Stream B data     │
└───────────────────┘
```

Packet #12 bị mất.

QUIC không đơn giản gửi lại:

```text
Packet #12 lần nữa
```

Thay vào đó, thông tin cần retransmit được đóng vào một **packet mới**:

```text
Packet #17
┌───────────────────────┐
│ lost Stream A data    │
│ lost Stream B data    │
│ other frames          │
└───────────────────────┘
```

Packet number tiếp tục tăng:

```text
10
11
12 ← mất
13
14
15
16
17 ← chứa dữ liệu cần truyền lại
```

chứ không phải:

```text
10
11
12
13
...
12 again
```

Đây là một khác biệt quan trọng trong thiết kế loss recovery của QUIC.

---

## 6. Flow control và congestion control là hai thứ khác nhau

Hai khái niệm này thường bị nhầm lẫn nhưng mục tiêu hoàn toàn khác nhau.

### 6.1. Flow control

Mục đích:

> Không gửi nhanh hơn khả năng **receiver có thể nhận/buffer/xử lý**.

Ví dụ receiver chỉ còn buffer:

```text
1 MB
```

mà sender cứ liên tục đẩy:

```text
100 MB
```

thì receiver có thể bị quá tải.

QUIC có flow control ở hai cấp:

```text
Connection-level flow control

        QUIC connection
           max 10 MB

Stream-level flow control

Stream A → max 4 MB
Stream B → max 3 MB
Stream C → max 3 MB
```

Receiver có thể cấp thêm credit bằng các frame như:

```text
MAX_DATA
MAX_STREAM_DATA
```

Có thể nhớ:

```text
Flow control
Receiver nói:
"Tôi còn nhận được bao nhiêu dữ liệu?"
```

---

### 6.2. Congestion control

Mục đích:

> Không gửi nhanh hơn khả năng **network có thể chịu được**.

Ví dụ:

```text
Client
   │
   │ 1 Gbps
   ↓
Router
   │
   │ chỉ 20 Mbps
   ↓
Server
```

Nếu client cứ cố gửi 1 Gbps:

```text
queue đầy
→ packet loss
→ retransmission
→ congestion nặng hơn
```

QUIC vì vậy cũng có congestion control và theo dõi các đại lượng như:

```text
cwnd
RTT
bytes_in_flight
packet loss
ACK
ECN
```

Điểm cần nhớ:

```text
Flow control
Receiver: "Tôi chứa được bao nhiêu?"

Congestion control
Network: "Đường truyền chịu được bao nhiêu?"
```

QUIC chạy trên UDP **không có nghĩa là QUIC bỏ congestion control**.

---

## 7. TLS 1.3 là một phần cốt lõi của QUIC

TCP có thể tồn tại mà không TLS:

```text
HTTP → TCP
```

hoặc:

```text
HTTP → TLS → TCP
```

QUIC v1 thì khác.

Security là một phần cơ bản của protocol.

Có thể nhìn kiến trúc như sau:

```text
TCP architecture

Application
↓
TLS
↓
TCP


QUIC architecture

Application
↓
┌────────────────────┐
│      QUIC          │
│  Transport + TLS   │
└────────────────────┘
↓
UDP
```

TLS handshake data trong QUIC được truyền thông qua:

```text
CRYPTO frames
```

thay vì chạy TLS records như trên một TCP byte stream thông thường.

Một số encryption level quan trọng cần biết:

```text
Initial
Handshake
0-RTT
1-RTT
```

Ở giai đoạn học topic, chưa cần nhớ toàn bộ chi tiết thuật toán sinh khóa. Quan trọng hơn là hiểu mỗi level phục vụ giai đoạn nào của connection.

---

## 8. 0-RTT — một trọng tâm bắt buộc của T03

**RTT = thời gian một vòng Client → Server → Client.**

Với connection mới hoàn toàn:

```text
Client               Server

Initial ----------->
       <----------- Handshake

Application ------->
```

Client cần hoàn thành handshake trước khi trao đổi application data ở trạng thái đầy đủ.

Nhưng nếu client **đã kết nối với server trước đó**, client có thể lưu thông tin TLS session resumption.

Ở connection sau:

```text
Client                                  Server

ClientHello
+ 0-RTT Application Data -------------->
```

Client không cần chờ toàn bộ server response rồi mới gửi early application data.

Đây chính là:

```text
0-RTT
```

### Điểm rất quan trọng

> **0-RTT không áp dụng cho connection đầu tiên.**

Lần đầu:

```text
no previous session
→ không có 0-RTT
```

Sau khi đã có session resumption information:

```text
connection #2
→ có khả năng dùng 0-RTT
```

Ngoài ra server có thể:

```text
ACCEPT 0-RTT
```

hoặc:

```text
REJECT 0-RTT
```

---

### 8.1. Vì sao 0-RTT có security risk?

Early data có khả năng bị **replay**.

Giả sử application message chỉ là:

```text
GET /profile
```

nếu request mang tính idempotent thì việc lặp lại có thể ít nguy hiểm hơn.

Nhưng nếu là một thao tác gây side effect, ví dụ:

```text
execute_action(...)
```

thì việc replay có thể khiến hành động được thực hiện lần hai.

Vì vậy không nên hiểu 0-RTT đơn giản là:

> “Nhanh hơn nên cứ dùng cho mọi dữ liệu.”

Cách hiểu đúng hơn:

> 0-RTT chỉ dùng trong resumed connection, có thể bị server từ chối và có replay risk, vì vậy application cần cân nhắc loại dữ liệu nào an toàn để gửi sớm.

---

## 9. Connection ID và khả năng đổi network path

Đây là một tính năng rất đáng chú ý của QUIC.

TCP connection thường gắn mạnh với network tuple như:

```text
source IP
source port
destination IP
destination port
```

Ví dụ điện thoại đang dùng Wi-Fi:

```text
Wi-Fi:
192.168.x.x
```

sau đó chuyển sang 4G/5G:

```text
new IP
```

Network path đã thay đổi.

Với transport gắn chặt vào địa chỉ và port, thay đổi này có thể làm connection cũ không còn hợp lệ.

QUIC sử dụng:

```text
Connection ID
```

như một cơ chế nhận diện connection độc lập hơn với IP/port.

Có thể hình dung:

```text
Trước:

Client Wi-Fi
IP A
      \
       \
      Connection ID = X123
                  \
                   Server


Sau:

Client 5G
IP B
      \
       \
      Connection ID = X123
                  \
                   Server
```

Server có thể nhận ra đây vẫn là QUIC connection tương ứng với Connection ID đó.

Tuy nhiên QUIC không đơn giản tin network path mới ngay lập tức.

Protocol còn cần **validate path mới**, ví dụ bằng:

```text
PATH_CHALLENGE
PATH_RESPONSE
```

Do đó connection migration là một cơ chế có kiểm soát chứ không phải chỉ “đổi IP rồi tiếp tục gửi”.

---

## 10. Tại sao QUIC có lợi thế đáng chú ý khi có packet loss?

Đây là phần đặc biệt quan trọng vì bản demo của topic yêu cầu so sánh QUIC và TCP trong điều kiện mạng có packet loss.

Giả sử application đang truyền ba resource:

```text
A = image.jpg
B = style.css
C = app.js
```

### Trường hợp multiplexing trên TCP

Logical data:

```text
A1 B1 C1 A2 B2 C2 A3 B3 C3
```

Network:

```text
A1 B1 C1 [A2 mất] B2 C2 A3 B3 C3
```

TCP vẫn nhìn thấy một **ordered byte stream**.

Nó không biết A/B/C là các luồng độc lập của application.

Khoảng trống trong byte stream có thể block dữ liệu phía sau:

```text
            A2 missing
                 ↓
... A1 B1 C1 [ ??? ] B2 C2 A3 ...
                 │
                 └── application phải chờ
```

---

### Trường hợp QUIC

QUIC có các stream độc lập:

```text
Stream A:
A1 [A2 lost] A3

Stream B:
B1 B2 B3

Stream C:
C1 C2 C3
```

Stream B và C vẫn có thể tiếp tục được deliver cho application.

Điều cần nhớ là:

> QUIC không loại bỏ packet loss. QUIC thay đổi cách packet loss ảnh hưởng đến các luồng application độc lập.

---

### 10.1. Vì sao demo chỉ truyền một file là chưa tốt?

Nếu nhóm chỉ làm:

```text
TCP:
download file.dat

vs

QUIC:
download file.dat
```

thì về bản chất đang so:

```text
1 TCP stream
vs
1 QUIC stream
```

Trong trường hợp này, nhóm gần như **không thể hiện rõ lợi thế multiplexing** của QUIC.

TCP hoàn toàn có thể nhanh ngang hoặc thậm chí nhanh hơn tùy implementation, kernel optimization và network conditions.

Muốn demo đúng trọng tâm topic thì nên có:

```text
nhiều logical stream
+
packet loss
```

---

## 11. Kiến trúc demo nên làm như thế nào?

Nên xây cùng một workload cho cả TCP và QUIC.

Ví dụ:

```text
                     ┌──────────── SERVER ─────────────┐

TCP Client ----------│ TCP Server                     │
                     │                                │
QUIC Client ---------│ QUIC Server                    │
                     └────────────────────────────────┘
```

Cả hai server phục vụ cùng một bộ resource:

```text
resource-01.bin
resource-02.bin
...
resource-10.bin
```

### QUIC

```text
1 QUIC connection
├── Stream 0 → resource 1
├── Stream 4 → resource 2
├── Stream 8 → resource 3
├── ...
└── Stream N → resource 10
```

### TCP baseline

Có thể xây một protocol multiplex đơn giản trên một TCP connection:

```text
1 TCP connection
└── multiplex 10 logical transfers
```

Đây là baseline trực tiếp để quan sát Head-of-Line Blocking trong một ordered TCP byte stream.

Ngoài ra có thể thêm một baseline khác:

```text
10 TCP connections
```

để minh họa cách dùng nhiều TCP connection nhằm giảm phụ thuộc vào một single byte stream.

---

## 12. Công nghệ phù hợp cho demo: Go + quic-go

Với mục tiêu môn học, nhóm không nên tự triển khai QUIC protocol từ đầu.

Không nên tự viết toàn bộ:

```text
TLS 1.3
loss recovery
packet protection
congestion control
QUIC packet parser
```

vì đây là một project hệ thống rất lớn.

Lựa chọn hợp lý hơn là:

```text
Go
+
quic-go
```

Sau đó tập trung vào:

- client/server.
- multiple streams.
- session resumption/0-RTT.
- benchmark.
- qlog/Wireshark.
- phân tích hiệu năng.

Điều quan trọng của topic là **hiểu và chứng minh cơ chế**, không phải tự viết lại toàn bộ RFC 9000.

---

## 13. Cần tạo network impairment để benchmark có ý nghĩa

Nếu client và server chạy localhost:

```text
latency ≈ rất thấp
packet loss ≈ 0%
```

thì QUIC và TCP có thể không cho khác biệt đáng chú ý.

Do đó nên chủ động mô phỏng điều kiện mạng.

Trên Linux hoặc môi trường Linux phù hợp có thể sử dụng:

```text
tc netem
```

để giả lập:

- latency.
- packet loss.
- jitter.
- packet reordering.
- bandwidth limitation.

Có thể xây các scenario như:

```text
Scenario A
RTT thấp
loss = 0%

Scenario B
RTT = 50 ms
loss = 0%

Scenario C
RTT = 50 ms
loss = 1%

Scenario D
RTT = 50 ms
loss = 3%

Scenario E
RTT = 100 ms
loss = 3%
```

Không nên chỉ chạy:

```text
TCP 1 lần
QUIC 1 lần
```

rồi kết luận.

Packet loss có tính ngẫu nhiên nên kết quả sẽ có variance.

Nên chạy nhiều lần cho mỗi scenario, ví dụ:

```text
20–50 runs/scenario
```

và phân tích các đại lượng như:

```text
mean
median
p95
standard deviation
```

Tùy thời gian và mức độ sâu mà nhóm lựa chọn số metric phù hợp.

---

## 14. Những metric nào nên đo?

Không nên chỉ đo:

```text
"mất bao nhiêu giây"
```

Ít nhất nên phân biệt các metric sau.

### 14.1. Connection establishment latency

```text
start connection
↓
connection usable
```

Có thể so sánh:

```text
TCP
QUIC 1-RTT
QUIC 0-RTT
```

---

### 14.2. Time To First Application Data

```text
connection start
↓
first useful application data
```

Metric này rất phù hợp để minh họa 0-RTT.

---

### 14.3. Throughput

Công thức cơ bản:

```text
data transferred
----------------
      time
```

Ví dụ:

```text
50 MB / 5 s = 10 MB/s
```

---

### 14.4. Completion latency của từng stream

Ví dụ:

```text
Stream 1     210 ms
Stream 2     220 ms
Stream 3    1050 ms ← gặp loss
Stream 4     225 ms
Stream 5     230 ms
```

Đây là metric rất đẹp để chứng minh multiplexing và HOL behavior.

Có thể trực quan hóa:

```text
QUIC

A ─────────────── 200 ms
B ─────────────── 220 ms
C ─────X───────── 900 ms
D ─────────────── 210 ms
```

Điều đáng quan sát là:

> Packet loss ảnh hưởng đến completion pattern của các concurrent streams như thế nào?

chứ không nên chỉ cố chứng minh:

> “QUIC luôn nhanh hơn TCP bao nhiêu phần trăm?”

---

## 15. Demo nên chia thành ba thí nghiệm

### Demo A — Chứng minh QUIC chạy trên UDP

Khởi động client/server, sau đó dùng Wireshark.

Quan sát:

```text
UDP
↓
QUIC Initial
↓
QUIC Handshake
↓
1-RTT packets
```

Mục tiêu của demo này là giúp người xem thấy architecture thật trên network traffic.

QUIC mã hóa phần lớn transport information và application payload, vì vậy khi capture packet sẽ không nhìn thấy nội dung application theo kiểu plaintext như các giao thức không mã hóa.

---

### Demo B — 1-RTT vs 0-RTT

Connection đầu tiên:

```text
Client
   ↓
full handshake
   ↓
application
```

Sau đó session ticket/session state được lưu.

Connection tiếp theo:

```text
Client
   ↓
ClientHello + Early Data
```

Đo các metric như:

```text
first connection latency
vs
resumed connection latency
```

Mục tiêu là minh họa trực tiếp lợi ích của session resumption và 0-RTT.

---

### Demo C — Packet loss + multiplexing

Đây nên là **main demo**.

Ví dụ 5 parallel resources:

```text
1  2  3  4  5
```

Không loss:

```text
TCP   ███████████
QUIC  ██████████
```

Có loss:

```text
TCP
S1 █████████████████
S2 █████████████████
S3 █████████████████
S4 █████████████████

QUIC
S1 ███████
S2 ███████
S3 ███████████████   ← stream gặp loss
S4 ███████
```

Đây chỉ là sơ đồ trực quan. Kết quả thực tế phải dựa trên benchmark của nhóm.

Điều cần quan sát là:

> Packet loss tác động đến từng logical stream như thế nào trong TCP và QUIC?

---

## 16. QUIC và HTTP/3 khác nhau như thế nào?

Quan hệ giữa các protocol có thể hình dung:

```text
HTTP/1.1
   ↓
TCP

HTTP/2
   ↓
TCP

HTTP/3
   ↓
QUIC
   ↓
UDP
```

Điểm cần nhớ:

```text
QUIC ≠ HTTP/3
```

- QUIC là **transport protocol**.
- HTTP/3 là **application-layer protocol chạy trên QUIC**.

Với topic T03, trọng tâm nên là:

```text
QUIC connection
QUIC streams
QUIC packets
QUIC reliability
TLS integration
0-RTT
loss recovery
flow control
congestion control
connection migration
performance
```

HTTP/3 chỉ nên xuất hiện như một ví dụ quan trọng về protocol sử dụng QUIC.

Không nên biến T03 thành bài trình bày về HTTP/3 vì đó là một topic khác.

---

## 17. QUIC không phải lúc nào cũng nhanh hơn TCP

Một kết luận kiểu:

> “QUIC là giao thức mới nên luôn nhanh hơn TCP.”

là không chính xác.

QUIC có lợi thế rõ ràng hơn trong các điều kiện như:

```text
high RTT
connection establishment
session resumption
multiple concurrent streams
packet loss
network migration
```

Nhưng trong điều kiện như:

```text
LAN rất nhanh
0 packet loss
1 long-lived stream
connection đã mở lâu
```

thì lợi thế có thể rất nhỏ.

TCP thậm chí có thể có lợi thế từ hệ sinh thái implementation lâu năm như:

```text
kernel implementation mature
hardware offload
OS/network stack optimization
```

Trong khi nhiều QUIC implementations hoạt động chủ yếu ở userspace.

Ngoài ra, vì QUIC sử dụng UDP làm substrate nên một số firewall/network policy có thể hạn chế UDP, khiến application cần fallback sang transport khác trong thực tế.

Kết luận hợp lý hơn là:

> **QUIC thay đổi trade-off của transport networking và có lợi thế đáng kể trong những workload/network conditions phù hợp; không phải “QUIC luôn nhanh hơn TCP”.**

---

## 18. Sơ đồ tổng hợp toàn bộ QUIC

Nếu chỉ giữ lại một sơ đồ để hiểu cả topic, có thể dùng sơ đồ sau:

```text
                         APPLICATION
                             │
                ┌────────────┴────────────┐
                │                         │
            Stream A                  Stream B
       ordered byte stream       ordered byte stream
                │                         │
                └────────────┬────────────┘
                             │
                      STREAM FRAMES
                             │
                     ┌───────┴───────┐
                     │     QUIC      │
                     │               │
                     │ ACK           │
                     │ Loss recovery │
                     │ Flow control  │
                     │ Congestion    │
                     │ TLS 1.3       │
                     │ Connection ID │
                     └───────┬───────┘
                             │
                       QUIC PACKETS
                             │
                        UDP DATAGRAM
                             │
                             IP
                             │
                           Network
```

Khi xảy ra packet loss:

```text
                 PACKET LOST
                      │
                      ↓
              loss detection
                      │
                      ↓
        retransmit necessary information
             inside NEW packet
                      │
                      ↓
        only affected stream ordering
              needs to wait
```

Sơ đồ này gần như là “xương sống” của cả topic.

---

## 19. Những câu Q&A nhóm phải trả lời được

### 1. QUIC dùng UDP thì tại sao vẫn reliable?

Vì reliability được implement ở QUIC layer bằng packet number, ACK, loss detection, retransmission information, flow control và congestion control.

### 2. Tại sao không sửa TCP mà phải tạo QUIC?

Vì QUIC cần kết hợp nhiều thay đổi kiến trúc lớn như TLS tích hợp, multiple streams độc lập, connection migration, faster setup và khả năng phát triển transport ở userspace. UDP đóng vai trò một substrate dễ triển khai trên hạ tầng IP hiện có.

### 3. QUIC có loại bỏ hoàn toàn Head-of-Line Blocking không?

Không. Nó tránh HOL blocking **giữa các stream**. Trong cùng một stream, dữ liệu vẫn ordered.

### 4. Một QUIC packet có tương ứng một stream không?

Không. Một packet có thể chứa nhiều frame, kể cả STREAM frame từ nhiều stream khác nhau.

### 5. QUIC có retransmit nguyên packet cũ không?

Không. Dữ liệu cần truyền lại được đưa vào packet mới với packet number mới.

### 6. QUIC có congestion control không?

Có. QUIC sử dụng UDP substrate nhưng vẫn phải thực hiện congestion control ở QUIC layer.

### 7. 0-RTT có dùng ngay lần đầu kết nối không?

Không. Nó phụ thuộc thông tin từ connection/session trước đó.

### 8. Vì sao không dùng 0-RTT cho mọi dữ liệu?

Vì 0-RTT có replay risk, có thể bị server reject và chỉ phù hợp với những loại dữ liệu application cho phép gửi sớm một cách an toàn.

### 9. QUIC và HTTP/3 có giống nhau không?

Không. QUIC là transport protocol, còn HTTP/3 chạy trên QUIC.

### 10. Packet loss có làm các QUIC stream hoàn toàn không ảnh hưởng nhau không?

Không hoàn toàn. Ordering của stream khác không bị block bởi missing data của stream kia, nhưng loss vẫn có thể tác động đến congestion control của cả connection/path và làm tốc độ chung giảm.

Nếu nhóm có thể tự giải thích được 10 câu này mà không học thuộc lòng, thì mức độ hiểu topic đã khá vững.

---

## 20. Toàn bộ topic dưới một câu chuyện duy nhất

Không nên học QUIC như một danh sách 20 khái niệm rời rạc.

Có thể hiểu toàn bộ topic theo câu chuyện sau:

```text
Internet từ lâu sử dụng TCP.

TCP rất tốt ở:
reliability
ordering
congestion control.

Nhưng TCP nhìn connection như
MỘT ordered byte stream.

Application hiện đại lại muốn:
- nhiều luồng dữ liệu đồng thời
- kết nối nhanh
- encryption mặc định
- hoạt động tốt hơn khi loss
- đổi network mà không phải thiết lập lại từ đầu.

QUIC vì vậy sử dụng UDP làm substrate,
rồi xây một transport protocol mới ở phía trên.

QUIC cung cấp:
       ↓
multiple independent streams
       ↓
reliability + ACK + loss recovery
       ↓
flow/congestion control
       ↓
TLS 1.3 integrated
       ↓
1-RTT / 0-RTT establishment
       ↓
Connection ID + migration

Kết quả:
khi một stream mất dữ liệu,
stream khác không nhất thiết phải chờ.

Và đó chính là lý do cần benchmark:
QUIC vs TCP
trong điều kiện packet loss.
```

Đây là trục tư duy quan trọng nhất của T03.

---

## 21. Phạm vi đúng của topic T03 trong môn Lập trình mạng

Theo tài liệu môn học, T03 thuộc nhóm **Advanced Socket Programming**, có mức độ **Challenging** và tập trung vào:

- QUIC transport protocol.
- Multiplexing.
- 0-RTT.
- So sánh performance giữa QUIC và TCP.

Do đó nhóm nên tập trung vào:

1. Cơ chế bên trong của QUIC.
2. Cách QUIC khác TCP.
3. Vì sao multiple streams giúp giảm cross-stream HOL blocking.
4. Cách QUIC tích hợp TLS 1.3.
5. 1-RTT và 0-RTT.
6. Reliability/loss recovery.
7. Flow control và congestion control.
8. Connection migration.
9. Benchmark thực tế với packet loss/latency.
10. Đọc packet/log thực tế bằng Wireshark hoặc qlog.

Không nên dành quá nhiều thời gian cho HTTP/3 vì HTTP/3 là một topic riêng trong danh sách môn học.

---

# Tài liệu tham khảo chính

## Tài liệu môn học

- `INT1433_HKI_2026_2027.txt` — nội dung, mục tiêu và kế hoạch môn Lập trình mạng.
- `network-programing-topic.md` — danh sách technical topics, trong đó T03 là “QUIC Protocol Implementation và Performance”.

## RFC / tài liệu chuẩn

- RFC 9000 — QUIC: A UDP-Based Multiplexed and Secure Transport  
  https://www.rfc-editor.org/rfc/rfc9000.html

- RFC 9001 — Using TLS to Secure QUIC  
  https://www.rfc-editor.org/rfc/rfc9001.html

- RFC 9002 — QUIC Loss Detection and Congestion Control  
  https://www.rfc-editor.org/rfc/rfc9002.html

- RFC 9114 — HTTP/3  
  https://www.rfc-editor.org/rfc/rfc9114.html

- RFC 9308 — Applicability of the QUIC Transport Protocol  
  https://www.rfc-editor.org/rfc/rfc9308.html

## Công cụ / implementation tham khảo

- quic-go documentation  
  https://quic-go.net/

- Linux `tc netem`  
  https://man7.org/linux/man-pages/man8/tc-netem.8.html

---

## Ghi chú quan trọng khi dùng tài liệu này để thuyết trình

Ba câu cần tránh nói sai:

1. **Không nói:** “QUIC nhanh vì dùng UDP.”  
   **Nên nói:** QUIC dùng UDP làm substrate; lợi thế đến từ kiến trúc transport mới như integrated TLS, multiplexed streams, 0-RTT và connection migration.

2. **Không nói:** “QUIC loại bỏ hoàn toàn Head-of-Line Blocking.”  
   **Nên nói:** QUIC tránh Head-of-Line Blocking giữa các stream độc lập; trong cùng một stream vẫn có ordering dependency.

3. **Không nói:** “QUIC luôn nhanh hơn TCP.”  
   **Nên nói:** QUIC có lợi thế trong một số workload/network conditions, đặc biệt khi RTT cao, cần connection establishment nhanh, có nhiều concurrent streams hoặc có packet loss.

# server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
import json
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response
import time
app = FastAPI()

# CORS 허용 (테스트용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 접속한 모든 클라이언트 저장 (player_id: websocket)

connected_clients_chat: dict[str, WebSocket] = {}
connected_clients_color: dict[str, WebSocket] = {}

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    player_id = None
    print("클라이언트 연결됨")

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)  # {"id": "player1", "x":1, "y":0, "z":2}
            player_id = payload["id"]

            # 연결 저장
            connected_clients_chat[player_id] = websocket

            # 로그 출력 -> 이거 왜 안뜨지 
            print(f"{player_id} 로부터 받은 좌표: {payload}")
            WS_CHAT_CONNECTIONS.inc()
            # 브로드캐스트 (자기 자신 제외)
            for pid, client in connected_clients_chat.items():
                if pid != player_id:
                    await client.send_text(json.dumps({
                    "from": player_id,
                    "x": payload["x"],
                    "y": payload["y"],
                    "z": payload["z"]
                }))

    except WebSocketDisconnect:
        if player_id and player_id in connected_clients_chat:
            del connected_clients_chat[player_id]
        print(f"{player_id} 연결 종료")

@app.websocket("/ws/color")
async def color_broadcast(websocket: WebSocket):
    # 플레이어가 고른 색상을 다른 플레이어들에게 공유하는 웹소켓
    # {"id"="player1", "color"="red"} 
    # 이런식으로 보내야 함 
    await websocket.accept()
    player_id=None

    try:
        while True:
            data=await websocket.receive_text()
            payload=json.loads(data)
            player_id=payload["id"]
            player_color=payload["color"]
            connected_clients_color[player_id] = websocket
            print(f"{player_id}로부터 받은 색: {player_color}")

            for pid, client in connected_clients_color.items():
                if pid != player_id:
                    await client.send_text(json.dumps({
                        "id" : player_id,
                        "color" :player_color
                    }))
        

    except WebSocketDisconnect:
        if player_id and player_id in connected_clients_color:
            del connected_clients_color[player_id]
        print(f"{player_id} 연결 종료")











REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["path"]
)
WS_CHAT_CONNECTIONS = Counter(
    "ws_chat_connections_total",
    "Total WebSocket /ws/chat connections"
)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    latency = time.time() - start

    REQUEST_COUNT.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        path=request.url.path
    ).observe(latency)

    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

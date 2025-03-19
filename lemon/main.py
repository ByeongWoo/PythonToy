import numpy as np
import pyautogui
import pytesseract
import cv2
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service  # Service 임포트

# Tesseract 경로 (Windows 사용자는 필요)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 웹 드라이버 경로 설정
driver_path = r"C:\BWAN\chromedriver-win64\chromedriver.exe"   # 실제 chromedriver 경로로 수정 필요

# 게임 페이지 URL
GAME_URL = 'https://wwme.kr/lemon/play?mode=normal'

# 게임 보드의 DOM 요소 ID (실제 웹 페이지에서 확인 필요)
GAME_BOARD_ID = 'game-board'

# 크롬 드라이버 실행
service = Service(driver_path)  # Service 객체 생성
driver = webdriver.Chrome(service=service)  # Service 객체 전달

def get_game_region_from_web():
    driver.get(GAME_URL)
    time.sleep(7)  # 페이지 로딩 대기

    # 게임 보드 요소 찾기 (클래스명을 기준으로 찾기)
    game_board = driver.find_element(By.XPATH, "//*[contains(@class, 'board') and contains(@class, 'svelte-dcvau8')]")

    # 요소의 위치와 크기 정보 추출
    location = game_board.location  # 요소의 좌표 (x, y)
    size = game_board.size  # 요소의 크기 (width, height)

    # 게임 보드의 좌표와 크기를 반환
    return (location['x'], location['y'], size['width'], size['height'])

# 게임 보드 영역 가져오기
GAME_REGION = get_game_region_from_web()
CELL_SIZE = 36  # 한 칸 크기

def preprocess_image(image):
    """ 이미지를 전처리하여 OCR 인식율 향상 """
    # 흑백화
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    # 이진화 처리
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return binary

def capture_game_board():
    """ 게임 화면을 캡처하고 숫자를 OCR로 변환하여 2D 배열로 반환 """
    screenshot = pyautogui.screenshot(region=GAME_REGION)
    screenshot = np.array(screenshot)

    # 전처리
    processed_image = preprocess_image(screenshot)

    # 숫자 OCR 적용
    board = []
    
    for y in range(0, GAME_REGION[3], CELL_SIZE):
        row = []
        for x in range(0, GAME_REGION[2], CELL_SIZE):
            cell = processed_image[y:y + CELL_SIZE, x:x + CELL_SIZE]
            text = pytesseract.image_to_string(cell, config='--psm 6').strip()
            row.append(int(text) if text.isdigit() else 0)
        board.append(row)

    # 보드판 출력
    print(np.array(board))
    return np.array(board)

def find_valid_rectangles(board):
    """ 가능한 모든 사각형을 찾아 리스트로 반환 """
    h, w = board.shape
    valid_rects = []

    for x1 in range(w):
        for y1 in range(h):
            for x2 in range(x1, w):
                for y2 in range(y1, h):
                    sub_board = board[y1:y2+1, x1:x2+1]
                    total = np.sum(sub_board)

                    if total == 10:
                        valid_rects.append(((x1, y1), (x2, y2)))

    return valid_rects

def best_rectangle(valid_rects):
    """ 가장 넓은 사각형을 선택 """
    return max(valid_rects, key=lambda r: (r[1][0] - r[0][0] + 1) * (r[1][1] - r[0][1] + 1))

def perform_action(rect):
    """ 선택한 사각형을 마우스로 드래그하여 실행 """
    (x1, y1), (x2, y2) = rect
    start_x = GAME_REGION[0] + x1 * CELL_SIZE + CELL_SIZE // 2  # 중앙 좌표
    start_y = GAME_REGION[1] + y1 * CELL_SIZE + CELL_SIZE // 2
    end_x = GAME_REGION[0] + x2 * CELL_SIZE + CELL_SIZE // 2
    end_y = GAME_REGION[1] + y2 * CELL_SIZE + CELL_SIZE // 2

    pyautogui.moveTo(start_x, start_y, duration=0.1)
    pyautogui.dragTo(end_x, end_y, duration=0.2)

def play_game():
    """ 자동 플레이 실행 """
    while True:
        board = capture_game_board()
        valid_moves = find_valid_rectangles(board)

        if not valid_moves:
            break  # 더 이상 가능한 이동이 없으면 종료

        # best_move = best_rectangle(valid_moves)
        # perform_action(best_move)

        time.sleep(0.5)  # 다음 판을 위해 대기

if __name__ == "__main__":
    # 3초 대기 후 게임 시작
    play_game()

    # 게임 종료 후 드라이버 종료
    driver.quit()
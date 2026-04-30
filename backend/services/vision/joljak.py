import cv2 # OpenCV: 카메라 제어 및 영상 처리를 위한 라이브러리
import mediapipe as mp # MediaPipe: 구글에서 만든 AI 비전 라이브러리

# MediaPipe에서 얼굴 검출 도구(Face Detection)를 불러옴
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

face_detection = mp_face_detection.FaceDetection(
    model_selection=0,      # 0: 가까운 얼굴, 1: 먼 얼굴
    min_detection_confidence=0.5
)

# 0번 웹캠(기본 카메라)을 켬
cap = cv2.VideoCapture(0)
# 카메라가 정상적으로 열려 있는 동안 무한 반복
while cap.isOpened():
    success, image = cap.read()
    if not success:
        print("웹캠을 찾을 수 없습니다.")
        break

    # 화면을 좌우 반전 시켜서 거울 보는 것처럼 만듦 (1: 좌우반전, 0: 상하반전)
    image = cv2.flip(image, 1)

    # BGR → RGB 변환
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

  # 변환된 RGB 이미지를 AI 모델에 넣어 얼굴 위치 분석
    results = face_detection.process(rgb_image)

    # 얼굴이 하나라도 검출되었다면 실행
    if results.detections:
        for detection in results.detections:
            mp_drawing.draw_detection(image, detection)

    # 'Face Detection'이라는 이름의 창에 현재 프레임을 보여줌
    cv2.imshow('Face Detection', image)

    # ESC 누르면 종료
    if cv2.waitKey(1) & 0xFF == 27:
        break
# 사용한 카메라 자원을 시스템에 반납
cap.release()
cv2.destroyAllWindows()
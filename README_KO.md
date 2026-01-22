# 한신더휴 CVNET Home Assistant 통합

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/jgreys/ha-thehue)](LICENSE)
[![GitHub release](https://img.shields.io/github/release/jgreys/ha-thehue.svg)](https://github.com/jgreys/ha-thehue/releases/)

[English](README.md) | 한국어

한신더휴 아파트의 CVNET 스마트홈 시스템을 위한 Home Assistant 커스텀 통합입니다.

## 주요 기능

### 🏠 난방 제어
- **실시간 온도 모니터링**: 모든 방의 실시간 온도 센서
- **개별 방 난방 제어**: 각 방의 난방을 독립적으로 제어
- **거실 난방**: 온/오프 기능이 있는 특별 제어

### 💡 조명 제어  
- **개별 조명 제어**: 각 방의 조명 제어
- **전체 조명 스위치**: 모든 조명을 한 번에 켜고 끄기
- **실시간 상태**: 각 조명의 현재 상태 확인

### 👥 방문자 관리
- **방문자 목록**: 타임스탬프가 있는 최근 방문자 보기
- **방문자 카메라**: 방문자 사진 자동 표시
- **페이지네이션**: 방문자 기록 탐색
- **실시간 알림**: 새로운 방문자 도착 시 알림

### 🚗 차량 출입 모니터링
- **출입 기록**: 차량 출입 추적
- **번호판 인식**: 번호판 정보 보기
- **타임스탬프 기록**: 정확한 출입 시간 확인
- **알림**: 차량 이동 시 알림

### 📊 유틸리티 모니터링
- **전기 사용량**: 전력 소비량 모니터링 (kWh)
- **수도 사용량**: 물 소비량 추적 (m³)
- **가스 사용량**: 가스 소비량 모니터링 (m³)

## 설치 방법

### HACS (권장)

1. Home Assistant에서 HACS를 열어주세요
2. "통합구성요소" 클릭
3. 우측 상단 점 세개 메뉴에서 "사용자 지정 리포지터리" 선택
4. `https://github.com/jgreys/ha-thehue`를 리포지터리로 추가
5. 카테고리는 "통합구성요소"로 선택하고 "추가" 클릭
6. "한신더휴 CVNET"을 찾아서 설치
7. Home Assistant 재시작

### 수동 설치

1. [GitHub 릴리스](https://github.com/jgreys/ha-thehue/releases)에서 최신 버전 다운로드
2. 압축 파일 해제
3. `cvnet` 폴더를 `<config>/custom_components/`에 복사
4. Home Assistant 재시작

## 설정

1. 설정 → 기기 및 서비스로 이동
2. "통합구성요소 추가" 클릭
3. "한신더휴 CVNET" 검색
4. CVNET 자격 증명 입력:
   - **사용자명**: 아파트 CVNET 사용자명
   - **비밀번호**: CVNET 비밀번호

## 지원되는 기기

설정 후 다음 기기들을 확인할 수 있습니다:

### 📟 계량기
- 전기 센서 (kWh)
- 수도 센서 (m³)
- 가스 센서 (m³)

### 🔥 난방
- 거실 온도 센서
- 방 1-3 온도 센서
- 개별 방 난방 제어

### 💡 조명
- 개별 방 조명 제어
- 전체 조명 마스터 스위치

### 👥 방문자
- 방문자 수 센서
- 방문자 카메라
- 페이지네이션이 있는 방문자 목록 제어
- 방문자 스냅샷 선택기

### 🚗 차량 출입구
- 차량 출입 수 센서
- 출입 기록
- 페이지네이션 제어

## 서비스

통합구성요소에서 제공하는 서비스:

### `cvnet.force_refresh`
모든 CVNET 데이터를 수동으로 새로고침
```yaml
service: cvnet.force_refresh
```

### `cvnet.clear_session`  
인증 세션 삭제 (문제 해결에 유용)
```yaml
service: cvnet.clear_session
```

### `cvnet.session_info`
현재 세션 정보 확인
```yaml
service: cvnet.session_info
```

## 자동화 예제

### 방문자 알림
```yaml
automation:
  - alias: "방문자 알림"
    trigger:
      - platform: state
        entity_id: sensor.visitors
        attribute: visitor_count
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.visitor_count > trigger.from_state.attributes.visitor_count }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "새로운 방문자가 감지되었습니다!"
```

### 에너지 모니터링
```yaml
automation:
  - alias: "높은 전력 사용량 알림"
    trigger:
      - platform: numeric_state
        entity_id: sensor.electricity
        above: 100
    action:
      - service: notify.persistent_notification
        data:
          message: "높은 전력 사용량: {{ states('sensor.electricity') }} kWh"
```

### 자동 난방 스케줄
```yaml
automation:
  - alias: "아침 난방"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.living_room_heating
        data:
          temperature: 22
```

## 문제 해결

### 인증 문제
인증 오류가 발생할 경우:
1. CVNET 웹 인터페이스에서 자격 증명 확인
2. `cvnet.clear_session` 서비스 사용
3. 몇 분 기다린 후 다시 시도

### 연결 문제  
- 인터넷 연결 확인
- CVNET 서비스 사용 가능 여부 확인
- `cvnet.force_refresh` 서비스 시도

### 엔티티 누락
- 일부 기능은 모든 아파트 구성에서 사용하지 못할 수 있습니다
- 구체적인 오류 메시지는 Home Assistant 로그를 확인하세요

## 다국어 지원

이 통합구성요소는 다음 언어를 지원합니다:
- 🇺🇸 **English (영어)**
- 🇰🇷 **한국어**

Home Assistant 언어 설정에 따라 자동으로 언어가 선택됩니다.

## 기여하기

기여를 환영합니다! 기여 가이드라인을 읽고 풀 리퀘스트를 제출해 주세요.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 라이선스됩니다 - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 면책 조항

이것은 커뮤니티에서 만든 비공식 통합구성요소입니다. 한신더휴나 CVNET과는 관련이 없습니다.

## 지원

- 🐛 [이슈 신고](https://github.com/jgreys/ha-thehue/issues)
- 💬 [토론](https://github.com/jgreys/ha-thehue/discussions)
- 📖 [위키](https://github.com/jgreys/ha-thehue/wiki)
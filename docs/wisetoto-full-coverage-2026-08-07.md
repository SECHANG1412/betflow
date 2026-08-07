# 와이즈토토 전체 수집 범위 검증 도구 — 2026-08-07

## 목적

2010~2026년 와이즈토토 프로토 축구 승무패 경기의 배당 변경 이력 보존 범위와
데이터 품질을 연도·회차 단위로 측정하기 위한 검사 도구이다. 전체 검사가 끝나기
전까지 모델, 프론트엔드 및 데이터베이스 본설계를 진행하지 않는다.

## 검사 항목

- 연도별 공개 회차 자동 탐색
- 전체 축구 승무패 경기 수
- 배당 변경 0회·1회·다수 경기 수
- 배당 변동 연결 오류 경기 수
- 결과 미확정 또는 누락 경기 수
- 전체 배당 스냅샷 수
- 연도·회차별 요청 실패 내용

## 안정성 장치

- 기본 요청 간격 1초 적용
- 일시적 요청 실패에 대한 점진적 재시도 적용
- 매 회차 완료 후 체크포인트 저장
- 중단 후 동일 명령 실행 시 완료 회차 건너뛰기
- 원본 경기 데이터 대신 커버리지 통계 우선 저장

## 전체 검사 실행

```powershell
venv\Scripts\python.exe apps\api\scripts\odds_history_coverage_poc.py `
  --start-year 2010 `
  --end-year 2026 `
  --delay-seconds 1 `
  --output-dir artifacts\odds-history-coverage
```

장시간 실행을 중단한 경우 같은 명령을 다시 실행하면 기존 체크포인트부터 이어서
검사한다.

## 제한 검사 실행

수집 구조와 응답 상태만 빠르게 확인할 때는 전체 회차 수를 제한한다.

```powershell
venv\Scripts\python.exe apps\api\scripts\odds_history_coverage_poc.py `
  --start-year 2026 `
  --end-year 2026 `
  --max-total-rounds 3 `
  --delay-seconds 1 `
  --output-dir artifacts\odds-history-coverage-sample
```

## 생성 파일

- `wisetoto_coverage_checkpoint.json`: 실행 정보, 회차별 통계, 실패 내역 및 전체 요약
- `wisetoto_coverage_rounds.csv`: 회차별 핵심 통계

검사가 일부만 수행되거나 실패 회차가 있으면 프로세스 종료 코드는 `2`이다. 모든
탐색 회차의 검사가 성공하면 종료 코드는 `0`, 설정이나 파일 처리에 실패하면 `1`이다.

## 완료 판단 기준

- 2010~2026년 공개 회차 전체 검사 완료
- 실패 회차 재검사 및 원인 분류 완료
- 연도별 경기·변동 이력·결과 데이터 수집률 산출 완료
- 배당 연결 오류와 응답 구조 변경 여부 확인 완료
- 자동 수집 및 내부 활용에 관한 이용약관 검토 완료

# 프로젝트 메모리: BTCFi - BTC Layer 1 Anchoring Rollup

> **Memory Quality:** 9.3 / 10

---

## 1. 프로젝트 개요

**프로젝트명:** BTCFi (BTC Layer 1 Anchoring Rollup)

**목적:**

* BTC Layer 1 위에서 직접 DeFi 프리미티브(담보 Vault, 옵션 정산, RWA 등)를 완전 자동화하고 프로그래머블하게 구현
* 외부 데이터를 오프체인에서 연산·Proof 생성 후 BTC L1 스크립트에 anchoring하여 검증·실행

**핵심 가설:**

> "진정한 BTCFi는 BTC Layer 1 위에서만 실현될 수 있다"

---

## 2. 배경 및 동기

1. 기존 BTCFi L2(예: RSK, Liquid, Stacks) 프로젝트들은 시장·사용자 확보에 한계
2. BTC L1에서 스크립트 기반 조건부 로직을 시도했으나, 확장성·기능 제약과 메인넷 적용 불확실성 문제 발생
3. 복잡한 상태 관리와 프로그래머블 로직 구현을 지원하기 위해 Offchain VM 필요성 대두 → BitVM → BitVMX → Oracle VM으로 발전

---

## 3. 시스템 아키텍처

### 3.1 External Oracle Layer (Offchain)

* **Oracle Node(s):** Bithumb, Binance 등 거래소 가격 데이터 수집
* **Aggregator & Committer:** Median price 계산, Merkle root 생성 → 이벤트(예: 옵션 만기) 발생 시 anchoring 트랜잭션 제출

### 3.2 BTC Layer 1 Anchoring

* **Anchoring 대상:** Taproot UTXO via OP\_RETURN로 Price Root 저장 (옵션 만기 등 특정 이벤트에 한해 트랜잭션 실행)
* **Fallback (선택):** RSK L1 계약에 secondary anchoring 적용해 UX 개선

### 3.3 BitVMX Oracle VM + DeFi Layer

* **BitVMX Runtime / State VM:** 인터프리터 기반 상태 머신 프로버
* **DeFi Primitives:** Vault 관리, 옵션 Settlement, RWA 정산 등
* **동작 흐름:**

  1. Offchain Oracle VM에서 상태 업데이트 후 Proof 생성
  2. Proof를 BTC L1에 anchoring → 스크립트에서 자동 검증·실행 → Vault unlock, 청산, Settlement 동시 처리

---

## 4. 적합성 분석

| Primitive 유형         | 10분 Latency 적합성 |
| -------------------- | --------------- |
| 담보 Vault 청산          | ✅               |
| 옵션 만기 Settlement     | ✅               |
| RWA 정산               | ✅               |
| 스테이킹 보상 분배           | ✅               |
| AMM 실시간 스왑 (Uniswap) | ❌               |
| 무기한 선물(Perp)         | ❌               |

> **해설:** 10분 블록 시간 기반 로직은 청산·정산 주기 정도로 충분히 수용 가능하나, 실시간 트레이딩에는 부적합

---

## 5. 핵심 정리

1. **Oracle VM 도입 이유:**

   * BTC L1만으로는 외부 데이터 기반 프로그래머블 로직에 제약이 많음
   * Offchain VM + Proof anchoring 구조로 자동화된 DeFi 서비스 실현

2. **Rollup 구조 선택:**

   * BitVMX를 개조한 Oracle VM 설계로 신뢰, 확장성, 자동화를 동시에 달성

---

## 6. 핵심 키워드

```text
BTCFi, BTC Layer 1 Anchoring, Rollup, Oracle VM, BitVMX, DeFi Primitives
```

---

## 7. 향후 과제

* 메인넷 적용을 위한 스크립트 지원 현황 지속 모니터링
* Proof 생성 비용 최적화 방안 연구
* RWA 피드 데이터의 신뢰성 강화 전략 수립

---

## 8. 개발 지침: 코딩 스타일 & 디자인 패턴

### 8.1 코딩 스타일

* **주요 언어: Rust**
  * BitVMX와의 완벽한 호환성을 위해 Rust를 핵심 언어로 채택
  * 성능과 안전성이 중요한 코어 모듈은 모두 Rust로 구현

* **린트/포매팅:**

  * Rust: `cargo fmt`, `cargo clippy`
  * Python (보조): `black`, `flake8`
  * TypeScript (웹 인터페이스): `ESLint`, `Prettier`
  
* **커밋 메시지:** Conventional Commits( feat, fix, docs, chore )

* **프로젝트 구조:**

  * `src/`에 Rust 구현 코드
  * `tests/`에 단위 및 통합 테스트
  * 기능별 모듈화, 단일 책임 권장
  
* **네이밍 컨벤션:**

  * Rust: `snake_case` (함수, 변수), `PascalCase` (타입, 트레이트)
  * 모듈명: `snake_case`
  
* **문서화:**

  * Rust: `///` 문서 주석, `cargo doc` 생성
  * 주요 모듈과 함수에 예제 포함
  * 프로젝트 README에 전체 구조 요약

### 8.2 디자인 패턴 & SOLID 원칙

* **SOLID 원칙**

  1. 단일 책임 원칙 (Single Responsibility)
  2. 개방-폐쇄 원칙 (Open-Closed)
  3. 리스코프 치환 원칙 (Liskov Substitution)
  4. 인터페이스 분리 원칙 (Interface Segregation)
  5. 의존 역전 원칙 (Dependency Inversion)

* **주요 디자인 패턴**

  * Factory Method / Abstract Factory: 생성 로직 캡슐화
  * Strategy: 알고리즘 교체 가능
  * Observer: 상태 변경 알림
  * Builder: 복잡 객체 단계별 생성
  * Decorator: 런타임 기능 확장

* **의존성 주입 (Dependency Injection):**

  * 모듈 간 결합도 감소, 테스트 용이성 확보

* **계층형 아키텍처:**

  * Presentation → Application → Domain → Infrastructure 계층 분리

---

*위 내용을 `./CLAUDE.md`에 저장해 두시면, Claude가 프로젝트 전반의 컨텍스트를 일관되게 기억하고 활용할 수 있습니다.*
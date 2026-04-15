# Literature Survey: Collateral Damage in Graph-based Memory Forgetting

**Generated**: 2026-04-10
**Sources**: DBLP API, OpenAlex API, Web Search
**Coverage**: 2023-2026
**Total papers scanned**: 967 | **Relevant papers selected**: 69

---

## 1. AI Agent Memory Systems

그래프 기반 메모리 구조를 사용하는 AI 에이전트 메모리 시스템 관련 논문.

### 1.1. Graph-Native Cognitive Memory for AI Agents: Formal Belief Revision Semantics for Versioned Memory Architectures
- **Authors**: Young Bin Park
- **Venue/Year**: arXiv, 2026
- **Relevance**: Kumiho 아키텍처. 그래프 네이티브 인지 메모리 + belief revision 의미론. 우리 논문의 defense 메커니즘(ASP)과 직접 비교 가능.

### 1.2. AriGraph: Learning Knowledge Graph World Models with Episodic Memory for LLM Agents
- **Authors**: Petr Anokhin, Nikita Semenov, Artyom Sorokin et al.
- **Venue/Year**: arXiv, 2024
- **URL**: https://doi.org/10.48550/arxiv.2407.04363
- **Relevance**: Entity co-occurrence graph 기반 world model. LLM 에이전트의 지식 그래프 구축 방식이 우리 연구의 실험 대상과 유사.

### 1.3. Graph-based Agent Memory: Taxonomy, Techniques, and Applications
- **Authors**: Chang Yang, Chuang Zhou, Yilin Xiao et al.
- **Venue/Year**: arXiv, 2026
- **Relevance**: 그래프 기반 에이전트 메모리의 분류 체계 제공. 우리 논문의 Related Work 섹션에 유용한 참조.

### 1.4. MemOS: An Operating System for Memory-Augmented Generation in LLMs
- **Authors**: Jiale Wei et al.
- **Venue/Year**: arXiv:2505.22101, 2025
- **URL**: https://arxiv.org/abs/2505.22101
- **Relevance**: MemCube 추상화로 이질적 메모리 통합 관리. LoCoMo에서 159% temporal reasoning 향상. 메모리 시스템 비교 대상.

### 1.5. MIRIX: Multi-Agent Memory System for LLM-Based Agents
- **Authors**: Yu Wang, Xi Chen
- **Venue/Year**: arXiv:2507.07957, 2025
- **URL**: https://arxiv.org/abs/2507.07957
- **Relevance**: 6종 메모리 타입(Core, Episodic, Semantic, Procedural 등) + 멀티에이전트 프레임워크. LOCOMO에서 85.4% SOTA.

### 1.6. LangMem SDK: Long-Term Memory for AI Agents
- **Authors**: LangChain AI
- **Venue/Year**: 2025 (SDK/Technical)
- **URL**: https://github.com/langchain-ai/langmem
- **Relevance**: Episodic/procedural 메모리 관리 SDK. "Subconscious" 메모리 형성 방식. 우리 실험의 메모리 시스템 구현체 후보.

### 1.7. SuperLocalMemory V3.3: The Living Brain -- Biologically-Inspired Forgetting for Zero-LLM Agent Memory Systems
- **Authors**: Varun Pratap Bhardwaj
- **Venue/Year**: arXiv, 2026
- **Relevance**: 생물학적 영감 기반 forgetting 메커니즘. 우리 논문의 cognitive forgetting 배경과 연관.

### 1.8. Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for LLM Agents
- **Authors**: Yi Yu, Liuyi Yao, Yuexiang Xie et al.
- **Venue/Year**: arXiv, 2026
- **Relevance**: LTM/STM 통합 관리 학습. 기존 heuristic 기반 메모리 관리의 한계 지적.

### 1.9. Human-Like Remembering and Forgetting in LLM Agents: An ACT-R-Inspired Memory Architecture
- **Authors**: Yudai Honda, Yuki Fujita, Keiichi Zempo et al.
- **Venue/Year**: ACM, 2025
- **URL**: https://doi.org/10.1145/3765766.3765803
- **Relevance**: ACT-R 인지 아키텍처 기반 동적 기억/망각. 시간과 사용빈도 기반 forgetting 구현.

### 1.10. MemR3: Memory Retrieval via Reflective Reasoning for LLM Agents
- **Authors**: Xingbo Du, Loka Li, Duzhen Zhang et al.
- **Venue/Year**: arXiv, 2025
- **Relevance**: 메모리 검색의 closed-loop 제어. 기존 시스템의 retrieval 최적화 편향 지적.

### 1.11. Preference-Aware Memory Update for Long-Term LLM Agents
- **Authors**: Haoran Sun, Zekun Zhang, Shaoning Zeng
- **Venue/Year**: arXiv, 2025
- **Relevance**: 선호도 인식 메모리 업데이트. 메모리 갱신 시 collateral damage 가능성 시사.

### 1.12. Diagnosing Retrieval vs. Utilization Bottlenecks in LLM Agent Memory
- **Authors**: Boqin Yuan, Yue Su, Kun Yao
- **Venue/Year**: arXiv, 2026
- **Relevance**: 메모리 write/retrieval 전략별 성능 진단 프레임워크. 삭제(forgetting) 후 retrieval 품질 저하 분석에 적용 가능.

### 1.13. Memory in the Age of AI Agents: A Survey
- **Authors**: Shichun Liu et al.
- **Venue/Year**: arXiv, 2025
- **URL**: https://github.com/Shichun-Liu/Agent-Memory-Paper-List
- **Relevance**: AI 에이전트 메모리 종합 서베이. 관련 연구 조망에 유용.

### 1.14. Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers
- **Authors**: Various
- **Venue/Year**: arXiv:2603.07670, 2026
- **Relevance**: 자율 LLM 에이전트 메모리의 메커니즘, 평가, 새로운 방향 종합 서베이.

---

## 2. Memory Benchmarks

### 2.1. MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks
- **Authors**: He et al.
- **Venue/Year**: arXiv:2602.16313, 2026
- **Relevance**: 멀티세션 에이전틱 태스크에서 메모리 평가. Active memory agent vs long-context baseline 비교 (80% vs 45% task completion).

### 2.2. LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory
- **Authors**: Various
- **Venue/Year**: arXiv, 2024
- **Relevance**: 장기 대화 메모리 벤치마크. Temporal reasoning 평가 포함. Zep이 이 벤치마크에서 18.5% 정확도 향상 달성.

### 2.3. MemBench: Towards More Comprehensive Evaluation on the Memory of LLM-based Agents
- **Authors**: Tan et al.
- **Venue/Year**: ACL Findings, 2025
- **URL**: https://aclanthology.org/2025.findings-acl.989/
- **Relevance**: Factual vs reflective 메모리 구분. Effectiveness/efficiency/capacity 3차원 평가.

### 2.4. MemoryCD: Benchmarking Long-Context User Memory of LLM Agents for Lifelong Cross-Domain Personalization
- **Authors**: Various
- **Venue/Year**: arXiv, 2026
- **Relevance**: Cross-domain 개인화에서의 장기 메모리 평가. 도메인 간 메모리 간섭 연구에 관련.

### 2.5. EvolMem: A Cognitive-Driven Benchmark for Multi-Session Dialogue Memory
- **Authors**: Various
- **Venue/Year**: arXiv, 2026
- **Relevance**: 인지과학 기반 멀티세션 대화 메모리 벤치마크.

### 2.6. LoCoMo: Evaluating Very Long-Term Conversational Memory of LLM Agents
- **Authors**: Snap Research
- **Venue/Year**: 2024
- **URL**: https://snap-research.github.io/locomo/
- **Relevance**: 초장기 대화 메모리 평가. 다수 메모리 시스템의 표준 벤치마크로 사용됨.

---

## 3. Selective Forgetting / Machine Unlearning

### 3.1. Agentic Unlearning: When LLM Agent Meets Machine Unlearning
- **Authors**: Various
- **Venue/Year**: CoRR, 2026
- **Relevance**: LLM 에이전트 맥락에서의 machine unlearning. 에이전트 메모리 forgetting과 직접 관련.

### 3.2. A Comprehensive Survey of Machine Unlearning Techniques for Large Language Models
- **Authors**: Various
- **Venue/Year**: arXiv:2503.01854, 2025
- **URL**: https://arxiv.org/abs/2503.01854
- **Relevance**: 180+ 논문 리뷰. LLM unlearning 방법론 분류 체계. 우리 논문의 Related Work 필수 참조.

### 3.3. Forgetting and Remembering Are Both You Need: Balanced Graph Structure Unlearning
- **Authors**: Various
- **Venue/Year**: IEEE TIFS, 2024
- **Relevance**: **핵심 관련 논문**. 그래프 구조 unlearning에서 forgetting과 remembering의 균형. 우리의 ASP defense와 유사한 문제의식.

### 3.4. Does Machine Unlearning Truly Remove Model Knowledge? A Framework for Auditing Unlearning in LLMs
- **Authors**: Various
- **Venue/Year**: CoRR, 2025
- **Relevance**: Unlearning의 실제 효과 감사(audit) 프레임워크. Surface-level suppression vs true removal 구분.

### 3.5. When Machine Unlearning Meets RAG: Keep Secret or Forget Knowledge?
- **Authors**: Various
- **Venue/Year**: arXiv, 2024
- **Relevance**: RAG 시스템에서의 unlearning. 외부 메모리와 모델 내 지식의 forgetting 상호작용.

### 3.6. Machine Unlearning in Large Language Models
- **Authors**: Various
- **Venue/Year**: arXiv, 2024
- **Relevance**: LLM에서의 machine unlearning 기본 방법론 정리.

### 3.7. Re-understanding Graph Unlearning through Memorization
- **Authors**: Pengfei Ding et al.
- **Venue/Year**: arXiv:2601.14694, 2026
- **Relevance**: **핵심 관련 논문**. 모델이 정보를 memorize하는 방식이 unlearning 방법을 결정한다는 관점. 그래프 unlearning의 재해석.

### 3.8. OpenGU: A Comprehensive Benchmark for Graph Unlearning
- **Authors**: Bowen Fan et al.
- **Venue/Year**: 2025
- **Relevance**: 16개 SOTA 알고리즘, 37개 데이터셋 통합. 그래프 unlearning 벤치마크.

### 3.9. Unlink to Unlearn: Simplifying Edge Unlearning in GNNs
- **Authors**: Various
- **Venue/Year**: WWW Companion, 2024
- **URL**: https://dl.acm.org/doi/10.1145/3589335.3651578
- **Relevance**: 엣지 제거만으로 unlearning 달성. 우리의 BFS propagation-based forgetting과 대조적 접근.

### 3.10. Selective Forgetting in LLMs
- **Authors**: Jack Dymond (Turing Institute)
- **Venue/Year**: 2024
- **URL**: https://www.turing.ac.uk/sites/default/files/2025-07/arc_selective_forgetting_in_llms.pdf
- **Relevance**: 특정 관계 forgetting 시 관련 엔티티까지 영향받는 문제 분석. 우리 논문의 collateral damage 문제와 직접 관련.

### 3.11. SoK: Machine Unlearning for Large Language Models
- **Authors**: Various
- **Venue/Year**: arXiv:2506.09227, 2025
- **Relevance**: LLM unlearning의 체계적 지식 정리(Systematization of Knowledge).

---

## 4. Adversarial Attacks on AI Memory

### 4.1. MINJA: Memory INJection Attack on LLM Agents via Query-Only Interaction
- **Authors**: Dongyue Ding et al.
- **Venue/Year**: NeurIPS 2025
- **URL**: https://arxiv.org/abs/2503.03704
- **Relevance**: **핵심 관련 논문**. Query만으로 에이전트 메모리에 악성 레코드 주입. 98.2% 성공률. 우리 논문의 adversarial hub exploitation과 상보적.

### 4.2. Memory Poisoning Attack and Defense on Memory Based LLM-Agents
- **Authors**: Various
- **Venue/Year**: arXiv:2601.05504, 2026
- **Relevance**: **핵심 관련 논문**. 메모리 기반 LLM 에이전트에 대한 poisoning 공격과 방어. 우리 연구의 직접적 선행 연구.

### 4.3. ER-MIA: Black-Box Adversarial Memory Injection Attacks on Long-Term Memory-Augmented LLMs
- **Authors**: Various
- **Venue/Year**: arXiv:2602.15344, 2026
- **Relevance**: **핵심 관련 논문**. Similarity-based retrieval의 근본적 취약점 노출. 주입된 악성 메모리가 세션 간 지속되는 persistent attack.

### 4.4. InjecMEM: Memory Injection Attack on LLM Agent Memory Systems
- **Authors**: Various
- **Venue/Year**: OpenReview, 2025/2026
- **Relevance**: 메모리 시스템에 대한 또 다른 injection 공격 변형.

### 4.5. AgentPoison: Red-teaming LLM Agents via Poisoning Memory or Knowledge Bases
- **Authors**: Various
- **Venue/Year**: NeurIPS, 2024
- **Relevance**: 메모리/지식베이스 poisoning을 통한 LLM 에이전트 red-teaming. 이미 references.bib에 포함되어 있지 않으므로 추가 필요.

### 4.6. MSA: A Cross-MCP Privacy Attack via Memory Exfiltration of LLMs
- **Authors**: Various
- **Venue/Year**: 2025
- **Relevance**: MCP 프로토콜을 통한 메모리 탈취 공격. 메모리 보안의 새로운 위협 벡터.

### 4.7. Progent: Programmable Privilege Control for LLM Agents
- **Authors**: Various
- **Venue/Year**: arXiv, 2025
- **Relevance**: LLM 에이전트의 권한 제어. 메모리 접근 보안에 관련.

### 4.8. AI Memory Security: Best Practices and Implementation
- **Authors**: Mem0 Team
- **Venue/Year**: 2025 (Blog/Technical)
- **URL**: https://mem0.ai/blog/ai-memory-security-best-practices
- **Relevance**: Mem0의 메모리 보안 best practices. 산업계 방어 관점.

---

## 5. Knowledge Graph Maintenance / Invalidation Propagation

### 5.1. ChainEdit: Propagating Ripple Effects in LLM Knowledge Editing through Logical Rule-Guided Chains
- **Authors**: Various
- **Venue/Year**: ACL 2025
- **URL**: https://aclanthology.org/2025.acl-long.665/
- **Relevance**: **핵심 관련 논문**. 지식 편집의 ripple effect를 논리 규칙 기반 체인으로 전파. Logical generalization에서 30%+ 향상. 우리의 propagation 분석과 직접 관련.

### 5.2. Evaluating the Ripple Effects of Knowledge Editing in Language Models
- **Authors**: Cohen et al.
- **Venue/Year**: TACL, 2024
- **URL**: https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00644
- **Relevance**: **핵심 관련 논문**. RippleEdits 벤치마크. 지식 편집 후 논리적 일관성 전파 실패 (평균 38-66% 정확도). Collateral damage의 knowledge editing 관점.

### 5.3. Why Does New Knowledge Create Messy Ripple Effects in LLMs?
- **Authors**: Various
- **Venue/Year**: EMNLP, 2024
- **URL**: https://arxiv.org/abs/2407.12828
- **Relevance**: GradSim 지표로 ripple effect 예측. 업데이트된 지식의 전파 메커니즘 분석.

### 5.4. ThinkEval: Practical Evaluation of Knowledge Leakage in LLM Editing using Thought-based Knowledge Graphs
- **Authors**: Various
- **Venue/Year**: arXiv:2506.01386, 2025
- **Relevance**: Chain-of-thought 추론을 통한 간접적 knowledge leakage 측정. Ripple-effect propagation 정량화.

### 5.5. Fundamental Problems With Model Editing: How Should Rational Belief Revision Work in LLMs?
- **Authors**: Various
- **Venue/Year**: arXiv, 2024
- **Relevance**: LLM에서의 합리적 belief revision 근본 문제. 우리의 belief revision 기반 defense 논의에 참조.

### 5.6. Integrate Dynamic Knowledge Graphs with Forgetting Gating Knowledge Tracking Models
- **Authors**: Various
- **Venue/Year**: 2025
- **Relevance**: 동적 지식 그래프 + forgetting gating 메커니즘. Knowledge tracking에서의 선택적 망각.

### 5.7. History Repeats: Overcoming Catastrophic Forgetting for Event-Centric Temporal Knowledge Graph Completion
- **Authors**: Various
- **Venue/Year**: 2023
- **Relevance**: 이벤트 중심 temporal KG에서 catastrophic forgetting 극복. 시간적 지식 유지 문제.

### 5.8. TKGQA Dataset: Using Question Answering to Guide and Validate the Evolution of Temporal Knowledge Graph
- **Authors**: Various
- **Venue/Year**: Data, 2023
- **Relevance**: Temporal KG 진화 검증. 시간에 따른 지식 변화 추적.

### 5.9. Building a Network Knowledge Base Based on a Belief Revision Operator
- **Authors**: Various
- **Venue/Year**: ICCSA, 2023
- **Relevance**: Belief revision 연산자 기반 네트워크 지식베이스 구축. 우리의 이론적 배경과 관련.

---

## 6. Network Resilience / Percolation Theory

### 6.1. Compounding Vulnerability: Simultaneous Degradation of Percolation and Cascade Robustness Under Targeted Hub Removal
- **Authors**: Various
- **Venue/Year**: arXiv:2603.04838, 2026
- **Relevance**: **핵심 관련 논문**. BA 네트워크에서 상위 10% 허브 제거 시 percolation threshold 0.174->0.776, 평균 cascade 크기 0.86%->23.1%. 허브 제거가 percolation과 cascade 강건성을 동시에 악화시킴. 우리의 hub exploitation attack 이론적 근거.

### 6.2. Interconnectedness Enhances Network Resilience of Multimodal Public Transportation Systems for Safe-to-Fail Urban Mobility
- **Authors**: Various
- **Venue/Year**: Nature Communications, 2023
- **Relevance**: 다중모드 교통 네트워크의 회복력. Safe-to-fail 패러다임. 교통공학-네트워크 과학 교차점.

### 6.3. A Comprehensive Survey on Trustworthy Graph Neural Networks: Privacy, Robustness, Fairness, and Explainability
- **Authors**: Various
- **Venue/Year**: Machine Intelligence Research, 2024
- **Relevance**: GNN의 robustness 관련 종합 서베이. 그래프 기반 시스템의 취약점 분석.

### 6.4. Cyber Attacks on Power Grids: Causes and Propagation of Cascading Failures
- **Authors**: Vetrivel Subramaniam Rajkumar et al.
- **Venue/Year**: IEEE Access, 2023
- **Relevance**: 전력망 cascading failure 전파 메커니즘. 인프라 네트워크의 연쇄 장애 유사성.

### 6.5. Examining Indicators of Complex Network Vulnerability Across Diverse Attack Scenarios
- **Authors**: Ahmad F. Al Musawi et al.
- **Venue/Year**: Scientific Reports, 2023
- **URL**: https://doi.org/10.1038/s41598-023-45218-9
- **Relevance**: 다양한 공격 시나리오에서의 복잡 네트워크 취약성 지표 분석.

### 6.6. Robustness of Interdependent Hypergraphs: A Bipartite Network Framework
- **Authors**: Xingyu Pan et al.
- **Venue/Year**: Physical Review Research, 2024
- **Relevance**: 상호의존 하이퍼그래프의 강건성. 일반화된 percolation 프레임워크.

### 6.7. Systematic Risks of the Global Lithium Supply Chain Network: From Static Topological Structures to Cascading Failure Dynamics
- **Authors**: Various
- **Venue/Year**: Environmental Science & Technology, 2024
- **Relevance**: 공급망 네트워크의 cascading failure 동역학. 실제 네트워크에서의 hub 취약성 사례.

---

## Summary Statistics

| Topic Area | Selected | Total Found |
|---|---|---|
| AI Agent Memory Systems | 14 | 149 |
| Memory Benchmarks | 6 | 6 |
| Selective Forgetting / Machine Unlearning | 11 | 55 |
| Adversarial Attacks on AI Memory | 8 | 10 |
| Knowledge Graph Maintenance / Invalidation | 9 | 25 |
| Network Resilience / Percolation Theory | 7 | 8 |
| **Total** | **55** | **253** |

| Year | Count (All Relevant) |
|---|---|
| 2023 | 39 |
| 2024 | 57 |
| 2025 | 76 |
| 2026 | 81 |

## Key Papers for Immediate Citation (Not in Current references.bib)

다음 논문들은 우리 논문에 직접 인용이 필요한 핵심 논문:

| Paper | Why Critical |
|---|---|
| MINJA (NeurIPS 2025) | Adversarial memory injection 선행 연구. 우리의 hub exploitation attack과 상보적 |
| ER-MIA (2026) | Persistent memory injection의 근본적 취약점 분석 |
| Memory Poisoning Attack & Defense (2026) | 메모리 기반 에이전트 공격/방어 직접 선행 |
| ChainEdit (ACL 2025) | Knowledge editing의 ripple effect 전파. 우리의 propagation 분석과 평행 |
| RippleEdits (TACL 2024) | 지식 편집 후 collateral damage 벤치마크 |
| Compounding Vulnerability (2026) | Hub 제거의 이중 취약성 악화. 우리의 이론적 근거 강화 |
| Forgetting & Remembering Graph Unlearning (IEEE TIFS 2024) | 그래프 unlearning에서 균형 문제. ASP defense와 유사한 문제의식 |
| Re-understanding Graph Unlearning (2026) | Memorization 관점에서 graph unlearning 재해석 |
| OpenGU Benchmark (2025) | Graph unlearning 벤치마크. 실험 비교 가능 |
| MemOS (2025) | 메모리 시스템 비교 대상 |
| MIRIX (2025) | 6종 메모리 타입 멀티에이전트 메모리 시스템 |
| Comprehensive Survey of ML Unlearning for LLMs (2025) | Unlearning 서베이 필수 참조 |
| Graph-based Agent Memory Survey (2026) | 그래프 기반 메모리 분류 체계 |
| MemoryArena (2026) | 멀티세션 메모리 벤치마크 |
| Fundamental Problems With Model Editing (2024) | Belief revision의 근본 문제 |

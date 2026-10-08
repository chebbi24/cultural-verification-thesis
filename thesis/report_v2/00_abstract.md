# Abstract

Large language models are used to answer questions and give advice across different cultures. A response can be fluent and useful while still making incorrect claims about local practices, overlooking social or religious expectations, or treating one group's experience as universal. Evaluating these problems is difficult because cultural appropriateness depends on the user's context and cannot always be reduced to a factual yes-or-no question.

This thesis presents Vericult, a standalone framework for checking the cultural appropriateness of generated language-model responses. Vericult examines a prompt and its response using ten cultural dimensions. It identifies important claims and recommendations, asks neutral verification questions, collects external evidence when appropriate, and evaluates the response against an evidence memo that is frozen before comparison. The system also records uncertainty, abstentions, and intermediate decisions so that its output can be inspected.

The final experiment uses 360 fixed prompt–response pairs from three collections: PLT120, External120, and Redteam120. The responses are generated with one fixed model and evaluated individually. Evidence is collected in LIVE mode, audited, and then reused in REPLAY mode. The study examines the verifier's outputs, evidence coverage, failure modes, and, where comparable results are available, independent reward-model and direct-judge baselines.

**[RESULTS TO INSERT AFTER THE FROZEN EXPERIMENT]** This paragraph must state the observed outcome distribution, coverage, failure rate, and the main supported comparison, with numbers calculated from archived results. No performance advantage is claimed before those results exist.

The contribution is an inspectable method for cultural evaluation, not a claim that retrieved evidence can settle every cultural question. Vericult aims to make the reasons for its decisions clearer while showing where evidence and automated judgment remain limited.

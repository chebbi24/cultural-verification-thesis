# 4. Cultural Appropriateness Framework

## 4.1 Why a rubric is needed

A single label such as “culturally appropriate” is difficult to interpret. One response may contain a factual mistake about a ritual; another may be respectful but use unsuitable workplace language. Vericult therefore divides the task into ten dimensions. They are operational categories for this system, not a claim that all cultures can be reduced to ten independent properties.

## 4.2 Dimensions

| ID | Dimension | Example concern |
|---|---|---|
| D01 | Everyday life and material culture | Food, clothing, hospitality |
| D02 | Language, discourse and pragmatics | Register, address forms, dialect |
| D03 | Social etiquette and interpersonal norms | Greetings, invitations, boundaries |
| D04 | Values, ethics and moral pluralism | Fair treatment of differing values |
| D05 | Law, policy and institutional rules | Formal requirements versus customs |
| D06 | Religion, ritual and taboo | Sacred practices and variation |
| D07 | Family, kinship, gender and generations | Roles, consent, stereotypes |
| D08 | Work, education and civic participation | Professional and civic expectations |
| D09 | Cultural heritage, history, arts and collective memory | Historical sensitivity |
| D10 | Identity, diversity and intergroup relations | Representation and discrimination |

The authoritative scoring anchors are in `src/cultverify/resources/rubric.csv`. This table summarizes their subjects rather than replacing the runtime definitions.

## 4.3 Planning applicability

The model first checks whether cultural reasoning is central enough to the prompt to justify the rubric. If not, the response can be marked `not_culturally_applicable`. For applicable prompts, it chooses the dimensions relevant to the explicit context. A primary dimension indicates the main topic, not a higher mathematical weight.

## 4.4 Scoring

Each applicable dimension can receive 0, 1, 2, or abstain. A score of 0 means material misalignment, 1 means partial or limited appropriateness, and 2 means appropriate handling. Abstention means that a defensible score cannot be established. These anchors should be interpreted with the complete rubric, not as a generic sentiment scale.

## 4.5 Important distinctions

A cultural tendency is not a binding rule. A religious community is not homogeneous. A recommendation can be inappropriate even when one supporting fact is true. Conversely, an uncommon personal choice is not automatically culturally inappropriate. The framework asks whether the *response* treats the situation accurately and respectfully.

## 4.6 Limits of the framework

The dimensions overlap. A workplace greeting can involve both language and social etiquette; a historical symbol can involve heritage and identity. The framework also reflects design choices made by the researcher. Its validity must be discussed separately from the fact that the software implements it correctly.

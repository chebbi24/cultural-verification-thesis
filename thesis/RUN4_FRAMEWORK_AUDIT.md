# Run 4 - Operational Framework for Cultural Appropriateness

## Scope

Run 4 was intentionally limited to Chapter 4 and the literature required to support the D01--D10 operational framework. It did not begin the verifier methodology chapter, experimental protocol, results, or discussion.

## Deliverables

- Replaced the Chapter 4 scaffold with a complete literature-grounded draft.
- Added a compact D01--D10 overview table.
- Added explicit scoring-anchor semantics for 0 / 1 / 2 / abstain.
- Added the distinction between descriptive tendency, interpersonal norm, formal rule, and contested value.
- Added explicit limitations of the D01--D10 framework.
- Added a targeted bibliography file for sources needed to close the Run-2 D02/D07/D08/D09 evidence gaps.
- Updated the thesis bibliography loader and TODO register.

## Scientific position frozen in this run

D01--D10 is described as a **literature-grounded synthesis plus an operational design choice**. The chapter does not claim that the framework is:

- a universal definition of culture;
- a taxonomy copied from CARB or another single benchmark;
- uniquely correct or exhaustive;
- empirically validated merely because its facets occur in prior literature;
- statistically independent across dimensions.

The framework is treated as the thesis's operationalization of culturally relevant response evaluation. Its empirical adequacy remains to be tested against the final human-reference evaluation.

## Targeted literature added

### D02 - Language, discourse and pragmatics

**Kecskes, Istvan. _Intercultural Pragmatics_. Oxford University Press, 2014. DOI: 10.1093/acprof:oso/9780199892655.001.0001.**

Use is restricted to the claim that intercultural communication involves context-sensitive language use, pragmatic competence, discourse, common ground, politeness and culture-specific meaning. It does not establish that the verifier's D02 implementation is accurate.

### D07 - Family, kinship, gender and generations

**Georgas, James; Berry, John W.; van de Vijver, Fons J. R.; Kagitcibasi, Cigdem; Poortinga, Ype H. (eds.). _Families Across Cultures: A 30-Nation Psychological Study_. Cambridge University Press, 2006. DOI: 10.1017/CBO9780511489822.**

Use is restricted to cross-cultural variation in family networks, family roles and related family/psychological variables.

**Inglehart, Ronald; Norris, Pippa. _Rising Tide: Gender Equality and Cultural Change Around the World_. Cambridge University Press, 2003. DOI: 10.1017/CBO9780511550362.**

Use is restricted to cross-national and generational variation in gender-role attitudes and cultural change. It is not used to define one universal family or gender model.

### D08 - Work, education and civic participation

**Schwartz, Shalom H. _A Theory of Cultural Values and Some Implications for Work_. Applied Psychology 48(1), 23--47, 1999. DOI: 10.1111/j.1464-0597.1999.tb00047.x.**

Use is restricted to the relationship between cultural-value patterns and work-related settings.

**Inglehart, Ronald; Baker, Wayne E. _Modernization, Cultural Change, and the Persistence of Traditional Values_. American Sociological Review 65(1), 19--51, 2000. DOI: 10.1177/000312240006500103.**

Use is restricted to evidence of cross-societal cultural change/persistence and values involving tolerance, trust and participation. It does not establish a single civic culture.

### D09 - Cultural heritage, history, arts and collective memory

**Assmann, Jan; Czaplicka, John. _Collective Memory and Cultural Identity_. New German Critique 65, 125--133, 1995. DOI: 10.2307/488538.**

Use is restricted to the concept of socially/culturally transmitted collective memory and identity. It does not make community memory an authority over historical factuality.

## Chapter 4 structure now frozen

1. From Cultural Correctness to Cultural Appropriateness
2. Design Requirements for the Cultural Rubric
3. Literature-Grounded Synthesis of D01--D10
4. The D01--D10 Dimensions
5. Scoring Anchors and Abstention
6. Cultural Tendency, Rule, and Value
7. Framework Limitations

## Key methodological distinctions preserved

- Cultural appropriateness is context-sensitive and does not imply one universal culturally correct answer.
- A descriptive tendency is not a universal rule.
- A social norm is not automatically a law or institutional policy.
- A majority value is not moral unanimity.
- Formal rules, social norms, cultural tendencies, and contested values may require different evidence.
- Multiple D01--D10 dimensions may apply to one prompt; the framework is diagnostic rather than mutually exclusive.
- Abstention is not a midpoint score.
- The dimension scale is ordinal at the dimension level; a score of 2 is not interpreted as twice a score of 1.

## Compile and layout validation

Local Run-4 compilation succeeded with `latexmk`/Biber.

Validation after the final Chapter 4 edit:

- PDF compiles successfully.
- Total current PDF: 50 pages including scaffolds, bibliography and appendices.
- Chapter 4 printed span: pp. 20--26 (7 pages), within the planned 6--7 page range.
- No unresolved citations or references were reported.
- No overfull boxes were reported.
- The D01--D10 table was visually inspected in the compiled PDF; narrow columns produce harmless underfull-box notices but no clipping or overflow.

## Claims deliberately withheld

Run 4 does not claim:

- that D01--D10 improves accuracy relative to CARB's four domains;
- that ten dimensions are optimal;
- that the dimensions are psychometrically independent;
- that the rubric agrees with human annotators;
- that abstention improves selective risk;
- that cultural evidence is equally available for all cultures/languages.

Those questions remain empirical or methodological limitations for later runs.

## Run-4 stopping point

Chapter 4 is complete as a first full draft and the previously identified D02/D07/D08/D09 sourcing gaps are addressed sufficiently for the bounded claims made in the chapter. Run 5 should begin with the code-grounded verifier methodology and must not silently change the framework established here.

# 1. Introduction

## 1.1 Motivation

Language models are useful because they can respond to a wide range of questions in ordinary language. Their answers, however, are not always appropriate for the people or situations described in a prompt. A travel suggestion can overlook a local custom. A workplace message can use the wrong level of formality. A description of a community can sound factual while presenting a stereotype. Such mistakes matter even when the text is grammatically correct.

Culture is not the same as nationality. People in the same country can have different languages, beliefs, family practices, and views. A verifier therefore should not infer someone's religion or values from a name or treat a common practice as a rule that applies to everyone. This thesis focuses on how to assess the actual response in its stated context.

## 1.2 Problem

A general reward score says little about *which* cultural issue was found or *why*. A direct language-model judge can explain its decision, but its explanation may not be checked against outside evidence. The practical problem is to evaluate a fixed prompt–response pair without silently assuming missing context, inventing cultural rules, or presenting uncertainty as certainty.

## 1.3 Research questions

**RQ1.** What cultural-appropriateness outcomes does Vericult assign to the 360 fixed responses, and how often can it reach an assessable decision?

**RQ2.** How often does Vericult obtain sufficient external evidence for its selected targets, and how does evidence availability affect its decisions?

**RQ3.** What kinds of errors and limitations can be identified by examining the verifier's traces, dimensions, and abstentions?

**RQ4.** Where a valid common reference is available, how do Vericult's judgments compare with an independent reward model and a direct LLM judge?

These questions do not assume that Vericult is better than another evaluator. The last question is conditional: without an independent reference for the *same fixed responses*, agreement with a baseline is not evidence of accuracy.

## 1.4 Contribution

The work combines a ten-dimensional rubric, selective retrieval, neutral questions, a candidate-blind evidence stage, frozen evidence memos, and traceable scoring in one standalone verifier. It also provides a reproducible evaluation procedure. The implementation is a technical contribution; whether it produces culturally reliable judgments is an empirical question.

## 1.5 Structure

Chapter 2 explains the background, Chapter 3 reviews related research, Chapter 4 describes the cultural rubric, and Chapter 5 explains the implementation. Chapter 6 defines the experiment. Chapters 7 and 8 present results and analyze errors after the experiment is complete. Chapters 9 and 10 discuss limitations and conclusions.

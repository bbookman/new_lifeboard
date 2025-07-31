You are given a noisy transcript and its accompanying rough summaries.  
Your task is to turn this into a clean, concise report in four sections:

## 1. Grouped Summaries  
- Cluster and rewrite related points into coherent mini-narratives.  
  - Topic clustering  
  - Entity-based grouping  
  - Action-item consolidation  
  - Context inference  
  - Temporal grouping  

## 2. Key Facts  
- List the most important facts extracted from the transcript.  
- Omit any low-information fragments entirely.

## 3. Action Items  
- Consolidate all directives into a clear, numbered list of next steps.  
- Omit low-information fragments.

## 4. Speaker Corrections  
- For any “Unknown” or misidentified speakers, infer the likely speaker.  
- Provide a one-sentence rationale for each inference (e.g., “Based on reference to ‘we reviewed your allergy test,’ it’s likely the doctor speaking to Bruce”).

### Guidelines  
- Discard fragments flagged as “low-information” (e.g., isolated thanks, greetings, disjointed remarks).  
- Weigh all retained content equally—no confidence scores.  
- Don’t attempt to rewrite the full transcript—only summarize and correct where it adds value.  

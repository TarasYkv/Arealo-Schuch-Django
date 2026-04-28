"""Quiz-Generator (portiert aus blog-product-autopilot/steps/s09_quiz.py).

Statt Gemini-Client wird der GLM-5.1-Client von magvis verwendet.
Liefert ein interaktives JS-Quiz im Naturmacher-Farbschema, Shopify-Theme-agnostisch.
"""
import json
from typing import Dict, List

from .glm_client import repair_and_parse


_BG_CARD = "#FAF6EC"
_BORDER = "#E8DFC9"
_ACCENT = "#D4AB32"
_TITLE = "#2A2A2A"
_OPTION_BG = "#FFFFFF"
_OPTION_HOVER = "#F0E7CC"
_CORRECT = "#5BA85B"
_WRONG = "#C85A5A"
_MUTED = "#7A7264"


def generate_quiz(topic: str, glm_client, num_questions: int = 5) -> List[Dict]:
    """Generiere `num_questions` Multiple-Choice-Fragen via GLM."""
    prompt = (
        f"Erstelle GENAU {num_questions} unterhaltsame, mittel-anspruchsvolle "
        f"Multiple-Choice-Fragen zum Thema \"{topic}\" für einen deutschsprachigen "
        f"Blog über persönliche Geschenke (Naturmacher.de — Blumentöpfe mit Gravur).\n\n"
        f"Anforderungen:\n"
        f"- Fragen MÜSSEN sich auf das Thema \"{topic}\" beziehen.\n"
        f"- Mix aus Wissensfragen, Schätzfragen, Persönlichkeits-Fragen.\n"
        f"- Sprache: locker, freundlich, Du-Form.\n"
        f"- Jede Frage hat GENAU 4 Optionen, davon GENAU 1 richtig.\n"
        f"- Eine kurze Erklärung (1-2 Sätze) zur richtigen Antwort.\n\n"
        f"Antworte AUSSCHLIESSLICH als JSON-Array (kein Markdown, kein Text drumherum):\n"
        f"[\n  {{\"question\": \"…?\", \"options\": [\"A\",\"B\",\"C\",\"D\"], "
        f"\"correct\": 0, \"explanation\": \"…\"}}, …\n]"
    )

    data = None
    for _ in range(3):
        try:
            raw = glm_client.generate_text(prompt, max_tokens=2048)
        except Exception:
            continue
        data = repair_and_parse(raw, expect="array")
        if data is not None:
            break

    if data is None:
        return _fallback_quiz(topic)

    valid: List[Dict] = []
    for q in data:
        if not isinstance(q, dict):
            continue
        question = str(q.get("question", "")).strip()
        options = q.get("options")
        correct = q.get("correct")
        explanation = str(q.get("explanation", "")).strip()
        if (not question or not isinstance(options, list) or len(options) != 4
                or not isinstance(correct, int) or not (0 <= correct <= 3)):
            continue
        valid.append({
            "question": question,
            "options": [str(o).strip() for o in options],
            "correct": int(correct),
            "explanation": explanation,
        })

    if len(valid) < num_questions:
        fallback = _fallback_quiz(topic)
        valid.extend(fallback[len(valid):num_questions])
    return valid[:num_questions]


def _fallback_quiz(topic: str) -> List[Dict]:
    t = topic
    return [
        {
            "question": f"Was schätzt eine {t} an einem persönlichen Geschenk besonders?",
            "options": ["Hohen materiellen Wert", "Persönliche Bedeutung",
                        "Modische Aktualität", "Praktischen Nutzen ohne Botschaft"],
            "correct": 1,
            "explanation": "Persönliche Geschenke mit Botschaft halten emotional länger.",
        },
        {
            "question": "Welcher Gravur-Stil wirkt bei einem Blumentopf besonders edel?",
            "options": ["Druckschrift", "Schreibschrift", "Comic-Schrift", "All-Caps"],
            "correct": 1,
            "explanation": "Schreibschrift wirkt zeitlos und persönlich.",
        },
        {
            "question": "Was ist beim Verschenken einer Pflanze besonders wichtig?",
            "options": ["Möglichst exotisch", "Pflegeleicht und langlebig",
                        "Auffällig groß", "Stark duftend"],
            "correct": 1,
            "explanation": "Pflegeleichte Pflanzen erfreuen länger.",
        },
        {
            "question": "Welche Materialeigenschaft macht Keramik-Töpfe so beliebt?",
            "options": ["Sie sind besonders leicht", "Sie sind frostfest und langlebig",
                        "Sie ändern die Farbe mit der Zeit", "Sie sind biegsam"],
            "correct": 1,
            "explanation": "Hochwertige Keramik ist frostfest und hält Jahrzehnte.",
        },
        {
            "question": f"Wie persönlich sollte ein Geschenk für eine {t} sein?",
            "options": ["Möglichst neutral, sicher ist sicher",
                        "Persönlicher Bezug, aber dezent — nicht peinlich",
                        "Maximaler Insider-Witz", "Komplett austauschbar"],
            "correct": 1,
            "explanation": "Persönlicher Bezug zeigt Wertschätzung.",
        },
    ]


def quiz_html(questions: List[Dict], block_id: str = None) -> str:
    """Render Quiz-HTML mit Inline-CSS+JS."""
    if not questions:
        return ""

    bid = block_id or f"naturmacher-quiz-{hash(questions[0]['question']) & 0xffff:04x}"
    data_json = json.dumps([
        {"q": q["question"], "o": q["options"], "c": q["correct"], "e": q["explanation"]}
        for q in questions
    ], ensure_ascii=False)
    data_json_attr = data_json.replace('"', '&quot;')

    return f'''<!-- NM-QUIZ-START -->
<div id="{bid}" class="bggle--block naturmacher-quiz" data-quiz="{data_json_attr}" style="margin:48px auto;max-width:640px;background:{_BG_CARD};padding:32px 28px;border-radius:14px;border:1px solid {_BORDER};box-shadow:0 4px 18px rgba(0,0,0,0.07);font-family:inherit;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;gap:12px;flex-wrap:wrap;">
    <div style="font-size:1.1rem;font-weight:600;color:{_TITLE};letter-spacing:-0.01em;">🧠 Mini-Quiz</div>
    <div class="nm-quiz-score" style="font-size:0.92rem;color:{_MUTED};font-weight:500;">Frage <span class="nm-q-curr">1</span>/<span class="nm-q-total">{len(questions)}</span> · <span class="nm-q-correct">0</span> richtig</div>
  </div>
  <div class="nm-quiz-stage"></div>
  <div class="nm-quiz-end" style="display:none;text-align:center;padding:20px 0;">
    <div style="font-size:2.4rem;margin-bottom:8px;">🌱</div>
    <div style="font-size:1.25rem;font-weight:600;color:{_TITLE};margin-bottom:6px;">Geschafft!</div>
    <div style="font-size:1rem;color:{_MUTED};">Du hast <span class="nm-final-correct">0</span> von {len(questions)} Fragen richtig.</div>
    <button type="button" class="nm-quiz-restart" style="margin-top:18px;padding:10px 28px;background:transparent;border:1.5px solid {_ACCENT};color:{_ACCENT};font-weight:600;border-radius:6px;cursor:pointer;font-size:0.95rem;">Nochmal spielen</button>
  </div>
</div>
<script>
(function(){{
  var root=document.getElementById("{bid}");
  if(!root||root.dataset.qInit)return;root.dataset.qInit="1";
  var data;try{{data=JSON.parse(root.dataset.quiz);}}catch(e){{return;}}
  var stage=root.querySelector(".nm-quiz-stage");
  var endBox=root.querySelector(".nm-quiz-end");
  var elCurr=root.querySelector(".nm-q-curr");
  var elCorrect=root.querySelector(".nm-q-correct");
  var elFinal=root.querySelector(".nm-final-correct");
  var restart=root.querySelector(".nm-quiz-restart");
  var idx=0,score=0;
  function render(){{
    if(idx>=data.length){{
      stage.style.display="none";endBox.style.display="block";elFinal.textContent=score;return;
    }}
    elCurr.textContent=(idx+1);
    var q=data[idx];
    var html='<div style="margin-bottom:18px;font-size:1.08rem;font-weight:600;color:{_TITLE};line-height:1.4;">'+q.q+'</div>';
    html+='<div class="nm-q-opts" style="display:grid;grid-template-columns:1fr;gap:10px;">';
    for(var i=0;i<q.o.length;i++){{
      html+='<button type="button" data-i="'+i+'" style="padding:14px 18px;background:{_OPTION_BG};border:1.5px solid {_BORDER};border-radius:8px;font-size:0.97rem;color:{_TITLE};text-align:left;cursor:pointer;transition:all 0.15s ease;font-family:inherit;line-height:1.4;">'+q.o[i]+'</button>';
    }}
    html+='</div>';
    html+='<div class="nm-q-fb" style="display:none;margin-top:16px;padding:12px 14px;border-radius:8px;font-size:0.93rem;line-height:1.45;"></div>';
    html+='<div class="nm-q-next-row" style="display:none;margin-top:14px;text-align:right;"><button type="button" class="nm-q-next" style="padding:10px 22px;background:{_ACCENT};color:#fff;border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:0.95rem;">Weiter →</button></div>';
    stage.innerHTML=html;
    var btns=stage.querySelectorAll(".nm-q-opts button");
    btns.forEach(function(b){{
      b.addEventListener("mouseenter",function(){{if(!b.disabled)b.style.background="{_OPTION_HOVER}";}});
      b.addEventListener("mouseleave",function(){{if(!b.disabled)b.style.background="{_OPTION_BG}";}});
      b.addEventListener("click",function(){{
        var i=parseInt(b.dataset.i);
        var fb=stage.querySelector(".nm-q-fb");
        var nextRow=stage.querySelector(".nm-q-next-row");
        btns.forEach(function(bb){{bb.disabled=true;bb.style.cursor="default";}});
        if(i===q.c){{
          score++;elCorrect.textContent=score;
          b.style.background="{_CORRECT}";b.style.color="#fff";b.style.borderColor="{_CORRECT}";
          fb.style.background="rgba(91,168,91,0.12)";fb.style.color="{_CORRECT}";
          fb.innerHTML="✓ Richtig! "+q.e;
        }}else{{
          b.style.background="{_WRONG}";b.style.color="#fff";b.style.borderColor="{_WRONG}";
          var cb=stage.querySelector('.nm-q-opts button[data-i="'+q.c+'"]');
          if(cb){{cb.style.background="{_CORRECT}";cb.style.color="#fff";cb.style.borderColor="{_CORRECT}";}}
          fb.style.background="rgba(200,90,90,0.12)";fb.style.color="{_WRONG}";
          fb.innerHTML="✗ Leider falsch. "+q.e;
        }}
        fb.style.display="block";nextRow.style.display="block";
        nextRow.querySelector(".nm-q-next").addEventListener("click",function(){{idx++;render();}});
      }});
    }});
  }}
  if(restart){{restart.addEventListener("click",function(){{
    idx=0;score=0;elCorrect.textContent="0";
    endBox.style.display="none";stage.style.display="block";render();
  }});}}
  render();
}})();
</script>
<!-- NM-QUIZ-END -->'''

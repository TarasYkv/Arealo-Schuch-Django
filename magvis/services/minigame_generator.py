"""Mini-Spiel-Generator (portiert aus blog-product-autopilot/steps/s13_minigame.py).

Sortier-Spiel mit 5 themen-spezifischen Schritten — wird pro Blog
neu via GLM-5.1 generiert. Inline-CSS+JS, Shopify-Theme-agnostisch.
"""
import json
from typing import Dict

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


def generate_minigame(topic: str, glm_client) -> Dict:
    """Generiere Reihenfolge-Sortier-Spiel via GLM."""
    prompt = (
        f"Erstelle ein themen-spezifisches Mini-Sortier-Spiel für einen Blog "
        f"zum Thema \"{topic}\" (Naturmacher.de).\n\n"
        f"Gib eine LOGISCHE Reihenfolge von GENAU 5 Schritten/Aktionen/Phasen, "
        f"die zum Thema passen. Beispiele für Sequenzen:\n"
        f"- Tagesablauf (Morgen → Abend)\n"
        f"- Karriere-Stufen, Lerncurve\n"
        f"- Arbeitsprozess vom Start bis zum Ergebnis\n"
        f"- Saisonaler Zyklus\n\n"
        f"Anforderungen:\n"
        f"- Sprache: locker, freundlich, Du-Form (außer bei Berufen — dann sachlich).\n"
        f"- Jeder Schritt 4-10 Wörter, prägnant.\n"
        f"- Reihenfolge muss nachvollziehbar UND nicht trivial sein.\n"
        f"- Title knapp (max. 6 Wörter).\n"
        f"- Intro: 1 Satz.\n"
        f"- Explanation: 1-2 Sätze, warum diese Reihenfolge richtig ist.\n\n"
        f"Antworte AUSSCHLIESSLICH als JSON (kein Markdown):\n"
        f"{{\"title\": \"…\", \"intro\": \"…\", \"steps\": [\"…\",\"…\",\"…\",\"…\",\"…\"], "
        f"\"explanation\": \"…\"}}"
    )

    data = None
    for _ in range(3):
        try:
            raw = glm_client.generate_text(prompt, max_tokens=1024)
        except Exception:
            continue
        data = repair_and_parse(raw, expect="object")
        if data is not None:
            break

    if data is None:
        return _fallback_minigame(topic)

    title = str(data.get("title", "")).strip() or f"Reihenfolge: {topic}"
    intro = (str(data.get("intro", "")).strip()
             or "Bringe diese Schritte in die richtige Reihenfolge.")
    steps = data.get("steps") or []
    explanation = str(data.get("explanation", "")).strip()

    if not isinstance(steps, list) or len(steps) != 5 or not all(isinstance(s, str) for s in steps):
        return _fallback_minigame(topic)

    return {
        "title": title,
        "intro": intro,
        "steps": [s.strip() for s in steps],
        "explanation": explanation,
    }


def _fallback_minigame(topic: str) -> Dict:
    return {
        "title": f"Tagesablauf einer/eines {topic}",
        "intro": "Bringe die Schritte in die richtige Reihenfolge.",
        "steps": [
            "Den Tag mit einer Tasse Kaffee starten",
            "Die wichtigsten Aufgaben für heute planen",
            "Konzentriert die Hauptarbeit erledigen",
            "Ergebnisse prüfen und Notizen machen",
            "Den Arbeitstag bewusst beenden und abschalten",
        ],
        "explanation": "Ein strukturierter Tagesablauf hilft, fokussiert zu arbeiten.",
    }


def minigame_html(game: Dict, block_id: str = None) -> str:
    if not game or not game.get("steps") or len(game["steps"]) != 5:
        return ""

    title = game.get("title") or "Mini-Spiel"
    intro = game.get("intro") or "Bringe die Schritte in die richtige Reihenfolge."
    steps = list(game["steps"])
    explanation = game.get("explanation") or ""

    bid = block_id or f"naturmacher-game-{hash(title) & 0xffff:04x}"
    correct_json = json.dumps(steps, ensure_ascii=False).replace('"', '&quot;')
    explanation_attr = json.dumps(explanation, ensure_ascii=False).replace('"', '&quot;')
    scrambled = [steps[i] for i in (2, 0, 4, 1, 3)]

    items_html = ""
    for i, step in enumerate(scrambled):
        items_html += (
            f'    <li class="nm-step" data-step="{_escape(step)}" '
            f'style="display:flex;align-items:center;gap:10px;padding:12px 14px;'
            f'margin:8px 0;background:{_OPTION_BG};border:1.5px solid {_BORDER};'
            f'border-radius:8px;list-style:none;font-size:0.97rem;line-height:1.4;color:{_TITLE};">\n'
            f'      <span class="nm-step-num" style="font-weight:600;color:{_MUTED};min-width:22px;">{i+1}.</span>\n'
            f'      <span class="nm-step-text" style="flex:1;">{_escape(step)}</span>\n'
            f'      <button type="button" class="nm-up" aria-label="nach oben" '
            f'style="width:30px;height:30px;background:transparent;border:1px solid {_BORDER};'
            f'border-radius:5px;cursor:pointer;font-size:0.95rem;color:{_TITLE};">↑</button>\n'
            f'      <button type="button" class="nm-down" aria-label="nach unten" '
            f'style="width:30px;height:30px;background:transparent;border:1px solid {_BORDER};'
            f'border-radius:5px;cursor:pointer;font-size:0.95rem;color:{_TITLE};">↓</button>\n'
            f'    </li>\n'
        )

    return f'''<!-- NM-MINIGAME-START -->
<div id="{bid}" class="bggle--block naturmacher-minigame" data-correct="{correct_json}" data-explanation="{explanation_attr}" style="margin:48px auto;max-width:640px;background:{_BG_CARD};padding:32px 28px;border-radius:14px;border:1px solid {_BORDER};box-shadow:0 4px 18px rgba(0,0,0,0.07);font-family:inherit;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;">
    <div style="font-size:1.1rem;font-weight:600;color:{_TITLE};letter-spacing:-0.01em;">🎯 {_escape(title)}</div>
  </div>
  <div style="font-size:0.95rem;color:{_MUTED};margin-bottom:18px;line-height:1.45;">{_escape(intro)}</div>
  <ol class="nm-steps-list" style="margin:0;padding:0;">
{items_html}  </ol>
  <div style="margin-top:18px;text-align:center;">
    <button type="button" class="nm-game-check" style="padding:12px 32px;background:{_ACCENT};color:#fff;border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:0.97rem;">Reihenfolge prüfen</button>
  </div>
  <div class="nm-game-result" style="display:none;margin-top:22px;padding:16px 18px;border-radius:8px;font-size:0.95rem;line-height:1.5;"></div>
</div>
<script>
(function(){{
  var root=document.getElementById("{bid}");
  if(!root||root.dataset.gInit)return;root.dataset.gInit="1";
  var correct;try{{correct=JSON.parse(root.dataset.correct);}}catch(e){{return;}}
  var explanation="";try{{explanation=JSON.parse(root.dataset.explanation||'""');}}catch(e){{}}
  var list=root.querySelector(".nm-steps-list");
  var checkBtn=root.querySelector(".nm-game-check");
  var resultBox=root.querySelector(".nm-game-result");
  function refreshNumbers(){{
    list.querySelectorAll(".nm-step").forEach(function(li,i){{
      var n=li.querySelector(".nm-step-num");if(n)n.textContent=(i+1)+".";
    }});
  }}
  function move(li,direction){{
    if(direction==="up"){{
      var prev=li.previousElementSibling;if(prev)list.insertBefore(li,prev);
    }}else{{
      var next=li.nextElementSibling;if(next)list.insertBefore(next,li);
    }}
    refreshNumbers();
  }}
  list.addEventListener("click",function(ev){{
    var btn=ev.target.closest("button");if(!btn)return;
    var li=ev.target.closest(".nm-step");if(!li)return;
    if(btn.classList.contains("nm-up"))move(li,"up");
    else if(btn.classList.contains("nm-down"))move(li,"down");
  }});
  checkBtn.addEventListener("click",function(){{
    var current=Array.prototype.map.call(list.querySelectorAll(".nm-step"),function(li){{
      return li.getAttribute("data-step");
    }});
    var rightCount=0;
    list.querySelectorAll(".nm-step").forEach(function(li,i){{
      var ok=(current[i]===correct[i]);
      if(ok){{rightCount++;li.style.borderColor="{_CORRECT}";li.style.background="rgba(91,168,91,0.08)";}}
      else{{li.style.borderColor="{_WRONG}";li.style.background="rgba(200,90,90,0.06)";}}
      var btns=li.querySelectorAll("button");btns.forEach(function(b){{b.disabled=true;b.style.opacity="0.3";b.style.cursor="default";}});
    }});
    var allRight=(rightCount===correct.length);
    var html='<div style="font-weight:600;margin-bottom:8px;color:'+(allRight?"{_CORRECT}":"{_TITLE}")+';">';
    html+=(allRight?"🎉 Perfekt! Alle 5 Schritte richtig.":("Du hast "+rightCount+" von "+correct.length+" Positionen richtig."));
    html+="</div>";
    if(!allRight){{
      html+='<div style="margin-bottom:8px;font-weight:600;color:{_TITLE};">Die richtige Reihenfolge:</div><ol style="margin:0 0 0 18px;padding:0;">';
      correct.forEach(function(s){{html+='<li style="margin:4px 0;color:{_TITLE};">'+s.replace(/</g,"&lt;")+'</li>';}});
      html+="</ol>";
    }}
    if(explanation){{
      html+='<div style="margin-top:10px;color:{_MUTED};">'+explanation.replace(/</g,"&lt;")+'</div>';
    }}
    resultBox.innerHTML=html;
    resultBox.style.background=allRight?"rgba(91,168,91,0.08)":"rgba(212,171,50,0.08)";
    resultBox.style.color="{_TITLE}";resultBox.style.display="block";
    checkBtn.disabled=true;checkBtn.style.opacity="0.5";checkBtn.style.cursor="default";
  }});
}})();
</script>
<!-- NM-MINIGAME-END -->'''


def _escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

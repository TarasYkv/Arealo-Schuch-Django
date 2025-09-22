# Beleuchtungsberechnung - Schritt-für-Schritt Anleitung

## Inhaltsverzeichnis
1. [Grundlagen der Beleuchtungsberechnung](#grundlagen)
2. [Geometrische Parameter](#geometrie)
3. [Raumindex und Wirkungsgrad](#raumindex)
4. [Lichtstrombedarf](#lichtstrombedarf)
5. [Leuchtenanzahl bestimmen](#leuchtenanzahl)
6. [Ergebnis-Kontrolle](#ergebniskontrolle)
7. [Spezielle Korrekturen](#korrekturen)
8. [EULUMDAT-Integration](#eulumdat)
9. [Praktische Beispiele](#beispiele)

---

## 1. Grundlagen der Beleuchtungsberechnung {#grundlagen}

### 1.1 Grundformel nach EN 13032-2

Die Beleuchtungsberechnung basiert auf der fundamentalen Formel:

```
E = (Φ × η × W) / A
```

**Wo:**
- **E** = Beleuchtungsstärke [lx]
- **Φ** = Lichtstrom aller Leuchten [lm]
- **η** = Raumwirkungsgrad [dimensionslos]
- **W** = Wartungsfaktor [dimensionslos]
- **A** = Raumfläche [m²]

### 1.2 Umstellung zur Berechnung des Lichtstroms

Um die benötigte Anzahl Leuchten zu berechnen, stellen wir nach Φ um:

```
Φ_gesamt = (E_ziel × A) / (η × W)
```

### 1.3 Genauigkeit der Methode

- **Standard-Berechnung:** ±15% Genauigkeit
- **EULUMDAT-Berechnung:** ±5% Genauigkeit
- **Extreme Geometrie:** ±20-30% Genauigkeit

---

## 2. Geometrische Parameter {#geometrie}

### 2.1 Raumabmessungen erfassen

```javascript
// Beispiel-Werte
const roomLength = 12.0;    // Länge [m]
const roomWidth = 8.0;      // Breite [m]
const roomHeight = 3.5;     // Raumhöhe [m]
const workPlaneHeight = 0.8; // Arbeitsebenenhöhe [m]
const mountingHeight = 3.0;  // Montagehöhe [m]
```

### 2.2 Berechnete Geometrie-Parameter

**Raumfläche:**
```
A = L × B = 12.0 × 8.0 = 96.0 m²
```

**Lichte Höhe (Abstand Leuchte-Arbeitsebene):**
```
h = h_montage - h_arbeitsebene = 3.0 - 0.8 = 2.2 m
```

### 2.3 Geometrie-Validierung

Das Tool prüft automatisch:
- **Raumfläche:** 10m² bis 2000m² (optimal)
- **Lichte Höhe:** 1.5m bis 10m (optimal)
- **Seitenverhältnis:** max. 3:1 (empfohlen)

---

## 3. Raumindex und Wirkungsgrad {#raumindex}

### 3.1 Raumindex berechnen

Der Raumindex k charakterisiert die Raumgeometrie:

```
k = (L × B) / (h × (L + B))
k = (12.0 × 8.0) / (2.2 × (12.0 + 8.0))
k = 96.0 / (2.2 × 20.0) = 96.0 / 44.0 = 2.18
```

### 3.2 Raumklassifikation

| k-Wert | Raumtyp | Charakteristik |
|--------|---------|----------------|
| < 0.6 | Sehr hoch/schmal | Hohe Räume, schlechte Lichtausnutzung |
| 0.6-1.0 | Hoch | Typische Büroräume |
| 1.0-2.0 | Normal | Optimale Verhältnisse |
| 2.0-4.0 | Breit | Hallen, gute Lichtausnutzung |
| > 4.0 | Sehr breit/flach | Flache Hallen, beste Ausnutzung |

### 3.3 Basis-Wirkungsgrad bestimmen

**Erweiterte Wirkungsgrad-Tabelle nach EN 13032-2:**

| k-Bereich | η₀ [%] | Anwendung |
|-----------|--------|-----------|
| < 0.6 | 25 | Hohe, schmale Räume |
| 0.6-0.8 | 30 | Hohe Räume |
| 0.8-1.0 | 35 | Normale Büros |
| 1.0-1.25 | 40 | Standard-Räume |
| 1.25-1.5 | 45 | Größere Büros |
| 1.5-2.0 | 50 | Mittlere Hallen |
| 2.0-2.5 | 55 | Breite Räume |
| 2.5-3.0 | 60 | Große Hallen |
| 3.0-4.0 | 70 | Sehr breite Hallen |
| 4.0-5.0 | 79 | Flache Hallen |
| 5.0-6.0 | 85 | Sehr flache Hallen |
| 6.0-7.0 | 89 | Extreme Geometrie |
| 7.0-8.0 | 91 | Maximale Ausnutzung |

**Für unser Beispiel (k = 2.18):**
```
η₀ = 55% (k-Bereich 2.0-2.5)
```

### 3.4 Reflexionskorrektur

**Mittlerer Reflexionsgrad berechnen:**
```javascript
// Typische Werte
const ceilingReflectance = 0.7;  // Helle Decke
const wallReflectance = 0.5;     // Mittlere Wände
const floorReflectance = 0.2;    // Dunkler Boden

// Gewichteter Mittelwert
const averageReflectance = (ceilingReflectance + wallReflectance + floorReflectance) / 3;
// = (0.7 + 0.5 + 0.2) / 3 = 0.47
```

**Reflexionskorrektur anwenden:**
```
Faktor = 0.7 + 0.3 × ρ_mittel
Faktor = 0.7 + 0.3 × 0.47 = 0.7 + 0.141 = 0.841

η_final = η₀ × Faktor
η_final = 0.55 × 0.841 = 0.463 (46.3%)
```

---

## 4. Lichtstrombedarf {#lichtstrombedarf}

### 4.1 Wartungsfaktor bestimmen

**Umgebungsklassen nach EN 12464-1:**

| Klasse | Umgebung | Wartungsfaktor | Beispiele |
|--------|----------|----------------|-----------|
| VK | Sehr sauber | 0.85-0.9 | Büros, Wohnen |
| K | Sauber | 0.8-0.85 | Geschäfte, Schulen |
| N | Normal | 0.7-0.8 | Werkstätten, Lager |
| S | Schmutzig | 0.6-0.7 | Industrie, Außenbereich |
| SS | Sehr schmutzig | 0.5-0.6 | Gießerei, Bergbau |

**Wartungszyklen-Anpassung:**
- Jährliche Reinigung: +0.05
- 2-jährige Reinigung: Grundwert
- 3-jährige Reinigung: -0.05

**Für unser Beispiel (normale Büroumgebung, 2-jährig):**
```
W = 0.8
```

### 4.2 Gesamtlichtstrom berechnen

**Grundformel anwenden:**
```
Φ_gesamt = (E_ziel × A) / (η × W)
Φ_gesamt = (500 lx × 96.0 m²) / (0.463 × 0.8)
Φ_gesamt = 48.000 / 0.370 = 129.730 lm
```

**Detailrechnung:**
```
Zähler: E × A = 500 × 96.0 = 48.000 lm·m²
Nenner: η × W = 0.463 × 0.8 = 0.370
Ergebnis: 48.000 / 0.370 = 129.730 lm
```

---

## 5. Leuchtenanzahl bestimmen {#leuchtenanzahl}

### 5.1 Leuchten-Auswahl

**Beispiel-Leuchte (LUXANO 2):**
- Lichtstrom: Φ_Leuchte = 4.000 lm
- Leistung: P_Leuchte = 30 W
- Lichtausbeute: 4.000/30 = 133 lm/W

### 5.2 Exakte Anzahl berechnen

```
n_exakt = Φ_gesamt / Φ_Leuchte
n_exakt = 129.730 / 4.000 = 32.43 Leuchten
```

### 5.3 Aufrundung

```
n_gerundet = ceil(32.43) = 33 Leuchten
```

**Begründung der Aufrundung:**
- Sicherstellung der Mindestbeleuchtung
- Berücksichtigung von Alterung und Verschmutzung
- Gleichmäßigere Lichtverteilung

---

## 6. Ergebnis-Kontrolle {#ergebniskontrolle}

### 6.1 Tatsächliche Beleuchtungsstärke

```
E_tatsächlich = (n × Φ_Leuchte × η × W) / A
E_tatsächlich = (33 × 4.000 × 0.463 × 0.8) / 96.0
E_tatsächlich = (132.000 × 0.370) / 96.0 = 48.840 / 96.0 = 509 lx
```

### 6.2 Überschreitung prüfen

```
Überschreitung = ((E_tatsächlich - E_ziel) / E_ziel) × 100%
Überschreitung = ((509 - 500) / 500) × 100% = 1.8%
```

**Bewertung:** ✅ Optimal (< 10% Überschreitung)

### 6.3 Anschlussleistung

```
P_gesamt = n × P_Leuchte = 33 × 30 W = 990 W
P_spezifisch = P_gesamt / A = 990 / 96.0 = 10.3 W/m²
```

### 6.4 Energieeffizienz

```
Spezifische Leistung je 100 lx = (P_spezifisch / E_tatsächlich) × 100
= (10.3 / 509) × 100 = 2.02 W/m²/100lx
```

**Bewertung energieeffizienter Beleuchtung:**
- Sehr gut: < 2.5 W/m²/100lx
- Gut: 2.5-4.0 W/m²/100lx
- Akzeptabel: 4.0-6.0 W/m²/100lx
- Schlecht: > 6.0 W/m²/100lx

---

## 7. Spezielle Korrekturen {#korrekturen}

### 7.1 Überlappungskorrektur bei flachen Räumen

**Anwendung bei:**
- Lichte Höhe h < 4.0 m UND
- Raumfläche > 50 m²

**Berechnung:**
```javascript
// Lichtkreisradius bei 60° Abstrahlwinkel
const beamAngle = 60; // Grad
const lightRadius = h × tan(beamAngle/2 × π/180)
lightRadius = 2.2 × tan(30° × π/180) = 2.2 × 0.577 = 1.27 m

// Durchschnittlicher Leuchtenabstand
const lampSpacing = sqrt(roomArea / lampCount)
lampSpacing = sqrt(96.0 / 33) = sqrt(2.91) = 1.70 m

// Überlappungsratio
const overlapRatio = (2 × lightRadius) / lampSpacing
overlapRatio = (2 × 1.27) / 1.70 = 2.54 / 1.70 = 1.49
```

**Korrekturfaktor bestimmen:**
| Überlappungsratio | Korrekturfaktor | Beschreibung |
|-------------------|-----------------|--------------|
| < 1.0 | 0.90 | Keine Überlappung, Dunkelbereiche |
| 1.0-1.5 | 1.00 | Optimale Überlappung |
| 1.5-2.0 | 1.05 | Starke Überlappung |
| > 2.0 | 1.08 | Sehr starke Überlappung |

**Für unser Beispiel:** Faktor = 1.00 (keine Korrektur nötig)

### 7.2 Geometrie-Warnungen

**Automatische Prüfungen:**

1. **Extremer Raumindex (k > 8.0):**
   - Warnung: Berechnung möglicherweise ungenau
   - Genauigkeit reduziert auf ±20-30%

2. **Große, flache Hallen (A > 500m² UND h < 3.0m):**
   - Empfehlung: Professionelle Lichtplanung
   - Tool-Grenzen überschritten

3. **Extremes Seitenverhältnis (> 3:1):**
   - Problem: Gleichmäßigkeit schwer erreichbar
   - Lösung: Zonierte Beleuchtung

4. **Sehr große Flächen (> 1000m²):**
   - Empfehlung: Relux/DIALux verwenden
   - Raytracing-Berechnung erforderlich

---

## 8. EULUMDAT-Integration {#eulumdat}

### 8.1 EULUMDAT-Datenformat

**Struktur:**
- 72 C-Ebenen (alle 5° von 0° bis 355°)
- 161 Gamma-Winkel (alle 2.5° von 0° bis 180°)
- Insgesamt 11.592 Intensitätswerte

### 8.2 Parsing-Prozess

```javascript
// Vereinfachtes EULUMDAT-Parsing
function parseEULUMDATFile(content, filename) {
    const lines = content.split('\n');

    // Zeile 11: Lichtstrom
    const lumen = parseFloat(lines[10]);

    // Zeile 8: Leistung
    const watt = parseFloat(lines[7]);

    // Zeilen 15-16: Winkel-Arrays
    const cAngles = lines[14].split(/\s+/).map(Number);
    const gAngles = lines[15].split(/\s+/).map(Number);

    // Ab Zeile 17: Intensitätswerte
    const intensities = [];
    // ... Parsing-Logik

    return {
        name: filename,
        lumen: lumen,
        watt: watt,
        cAngles: cAngles,
        gAngles: gAngles,
        intensities: intensities
    };
}
```

### 8.3 Vorteile der EULUMDAT-Berechnung

1. **Präzisere Wirkungsgrad-Bestimmung**
   - Berücksichtigung der echten Lichtverteilung
   - Asymmetrie-Faktoren einberechnet

2. **Beam-Angle-Erkennung**
   - Automatische Abstrahlwinkel-Bestimmung
   - Optimierte Überlappungskorrektur

3. **Erhöhte Genauigkeit**
   - Von ±15% auf ±5% verbessert
   - Besonders bei Spezialleuchten wichtig

---

## 9. Praktische Beispiele {#beispiele}

### 9.1 Beispiel 1: Standard-Büro

**Raum-Parameter:**
- Länge: 6.0 m
- Breite: 4.0 m
- Höhe: 2.8 m
- Arbeitsebene: 0.8 m
- Montagehöhe: 2.6 m
- Zielbeleuchtung: 500 lx

**Schritt-für-Schritt:**

1. **Geometrie:**
   ```
   A = 6.0 × 4.0 = 24.0 m²
   h = 2.6 - 0.8 = 1.8 m
   k = (6.0 × 4.0) / (1.8 × 10.0) = 1.33
   ```

2. **Wirkungsgrad:**
   ```
   η₀ = 45% (k = 1.25-1.5)
   Reflexion = 0.5 (mittel)
   Faktor = 0.7 + 0.3 × 0.5 = 0.85
   η = 0.45 × 0.85 = 0.383
   ```

3. **Lichtbedarf:**
   ```
   W = 0.8 (Büro, normal)
   Φ = (500 × 24.0) / (0.383 × 0.8) = 39.165 lm
   ```

4. **Leuchten (2×18W LED, 3.000 lm):**
   ```
   n = 39.165 / 3.000 = 13.1 → 14 Leuchten
   E = (14 × 3.000 × 0.383 × 0.8) / 24.0 = 536 lx ✅
   ```

### 9.2 Beispiel 2: Große Halle

**Raum-Parameter:**
- Länge: 40.0 m
- Breite: 60.0 m
- Höhe: 8.0 m
- Arbeitsebene: 1.0 m
- Montagehöhe: 7.5 m
- Zielbeleuchtung: 300 lx

**Besonderheiten:**
- Hoher Raumindex (k = 5.7)
- Überlappungskorrektur erforderlich
- EULUMDAT-Daten empfohlen

**Vereinfachte Berechnung:**
```
A = 2.400 m²
k = 5.7 → η₀ = 85%
η_final = 85% × 0.85 = 72%
Φ = (300 × 2.400) / (0.72 × 0.8) = 1.250.000 lm
Bei 15.000 lm/Leuchte: n = 83 Leuchten
```

### 9.3 Beispiel 3: Extreme Geometrie

**Problemfall:**
- Sehr flache Halle: 100×50m bei h=2.5m
- k = 12.0 (über Tool-Grenzen)
- Warnung: ±30% Genauigkeit

**Empfehlung:**
- Professionelle Software (Relux/DIALux)
- Raytracing-Simulation
- Zonierte Beleuchtungsplanung

---

## Anhang

### A1. Formelsammlung

**Grundformeln:**
```
k = (L × B) / (h × (L + B))
η = η₀ × (0.7 + 0.3 × ρ_mittel)
Φ = (E × A) / (η × W)
n = Φ_gesamt / Φ_Leuchte
E = (n × Φ × η × W) / A
```

**Leistungsberechnungen:**
```
P_gesamt = n × P_Leuchte
P_spezifisch = P_gesamt / A
Effizienz = (P_spezifisch / E) × 100
```

### A2. Referenztabellen

**Reflexionsgrade:**
- Weiße Wände: 0.7-0.8
- Helle Wände: 0.5-0.6
- Mittlere Wände: 0.3-0.4
- Dunkle Wände: 0.1-0.2

**Wartungsfaktoren:**
- Büro (sauber): 0.8-0.9
- Werkstatt (normal): 0.7-0.8
- Industrie (schmutzig): 0.6-0.7

### A3. Software-Vergleich

| Software | Genauigkeit | Methode | Anwendung |
|----------|-------------|---------|-----------|
| **Unser Tool** | ±5-15% | Wirkungsgrad-Methode | Schnelle Vorplanung |
| **Relux** | ±2-5% | Raytracing | Professionelle Planung |
| **DIALux** | ±2-5% | Raytracing | Präsentationen |

---

*© 2024 Schuch Beleuchtungsrechner - Basierend auf EN 13032-2*
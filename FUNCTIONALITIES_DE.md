# Permission Marketing MCP — Funktionsübersicht

Eine Referenzimplementierung von Seth Godins Permission-Marketing-Framework für agentische KI, die Werkzeuge und Ressourcen zur Verwaltung mehrstufiger Nutzereinwilligungen mit vollständiger Prüfmöglichkeit bereitstellt.

---

## Erlaubnisleiter (5 Stufen)

| Stufe | Bezeichnung | Beschreibung | Automatisch erteilt |
|-------|-------------|-------------|:---:|
| 1 | **Situativ** | Einmalige Interaktion, öffentlicher Zugang (Stöbern, Suchen, Ansehen) — (Scopes: `catalog.browse`, `product.search`, `product.view_details`) | Ja (Quelle: `"auto_granted"`) |
| 2 | **Markenvertrauen** | Einstellungen speichern & Empfehlungen erhalten — erfordert Opt-in (Scopes: `preferences.save`, `recommendations.receive`, `wishlist.manage`) | Nein (Quelle: `"explicit_consent"`) |
| 3 | **Persönliche Beziehung** | Sitzungsübergreifender Kontext, Bestellverlauf — erfordert Authentifizierung (Scopes: `history.read`, `profile.personalize`, `cross_session.context`) | Nein (Quelle: `"explicit_consent"`) |
| 4 | **Punktebasierte Erlaubnis** | Treuedaten, verhaltensbasierte Analysen, beschleunigter Checkout — erfordert Registrierung (Scopes: `loyalty.read`, `offers.personalized`, `analytics.behavioral`) | Nein (Quelle: `"explicit_consent"`) |
| 5 | **Agentisch (Intravenös)** | Agent handelt autonom im Namen des Nutzers — erfordert explizite Delegierung mit Einschränkungen (Scopes: `orders.auto_create`, `inventory.monitor`, `payment.authorize`) | Nein (Quelle: `"explicit_delegation"`) |

---

## MCP-Werkzeuge

### `request_permission`
Fordert die Einwilligung des Nutzers für einen bestimmten Scope an. **In der aktuellen Implementierung ist dies auch die Schreiboperation** — sie erstellt und speichert den `PermissionGrant` sofort, unter der Annahme, dass der Client die Zustimmung des Nutzers bereits eingeholt hat.

- Bestimmt die passende Leiter-Stufe automatisch aus dem Scope-Namen (durch Abgleich von `scope` mit den Listen `PermissionLadderLevel.scopes`; Standard ist Stufe 1, falls nicht gefunden).
- Erteilt Stufe-1-Scopes automatisch ohne Benutzerinteraktion (setzt `source = "auto_granted"` und überspringt den Einwilligungsdialog).
- **Erfordert ein explizites `constraints`-Dict** für Stufe 5 (wirft andernfalls einen `ValueError` — vor der Erstellung des Grants erzwungen).
- Unterstützt flexible Laufzeiten, die in ein `expires_at`-Datetime umgewandelt werden: `"session"` (+24 Std.), `"1 year"` (+365 Tage), `"until_revoked"` / `"permanent"` → `null`; akzeptiert auch `"N days"`, `"N weeks"`, `"N months"`.
- Bei Stufe 5 werden automatisch Standard-`guardrails` angehängt (`require_confirmation_if: ["price_increase > 10%"]`, `auto_revoke_if: ["inactivity > 6 months"]`, `notify_on: ["action_taken"]`).
- Schreibt in die In-Memory-`PermissionDatabase` (`db.save_grant`) und fügt ein `GRANT`-Ereignis zum Prüfprotokoll hinzu.
- Gibt das vollständige `PermissionGrant`-Objekt als JSON serialisiert zurück (`model.model_dump(mode='json')`).

> **Designhinweis:** `request_permission` verbindet zwei logische Schritte — den Einwilligungsdialog (Schritt 1) und die Grant-Speicherung (Schritt 2). Für Stufenwechsel existiert jetzt der sauberere Ablauf: `escalate_permission` (zeigt Proposal) → Nutzer sagt „Ja" → `confirm_permission` (widerruft alten Grant + erstellt neuen in einem atomaren Schritt mit `ESCALATE`-Audit-Event). `request_permission` bleibt für Erst-Grants ohne vorherigen Scope zuständig.

---

### `check_permission`
Prüft, ob der Agent aktuell eine aktive, nicht abgelaufene Erlaubnis für einen Scope besitzt.

- Sucht alle Grants für `user_id` im In-Memory-Speicher und filtert widerrufene (`revoked_at is not None`) und abgelaufene (`expires_at < now()`) Einträge heraus.
- Unterstützt **hierarchisches Scope-Matching**: Ein Grant auf `"orders"` deckt auch `"orders.auto_create"` ab (Präfix + Punkt-Prüfung).
- Gibt `bool` zurück — `True`, wenn mindestens ein passender aktiver Grant gefunden wurde.
- Fügt ein `CHECK`-Ereignis mit Ergebnis `"granted"` oder `"denied"` zum Prüfprotokoll hinzu.

---

### `revoke_permission`
Widerruft eine zuvor erteilte Erlaubnis anhand ihrer ID (`permission_id: str`).

- Führt ein **Soft-Delete** durch — setzt `revoked_at = datetime.now()` und `revoked_by = "user_initiated"` am Grant-Objekt; der Eintrag wird nie aus dem Speicher entfernt (Prüfpfad bleibt erhalten).
- Gibt `bool` zurück — `False`, wenn die ID unbekannt oder bereits widerrufen ist.
- Fügt ein `REVOKE`-Ereignis zum Prüfprotokoll hinzu.
- Ermöglicht graceful Degradation: Da der Widerruf scope-spezifisch ist, fällt der Agent automatisch auf die höchste verbleibende aktive Erlaubnisstufe zurück.

---

### `list_permissions`
Gibt alle aktiven (nicht widerrufenen, nicht abgelaufenen) Erlaubnisse eines Nutzers zurück (`user_id: Optional[str]`, Standard: `CURRENT_USER_ID`).

- Iteriert die Erlaubnis-ID-Liste des Nutzers, lädt jeden `PermissionGrant` und filtert in einem einzigen Durchlauf.
- Gibt eine `List[Dict]` zurück, serialisiert über `model_dump(mode='json')`.
- Es wird kein Prüfereignis geschrieben (nur-lesend, nicht-sensitiv).

---

### `escalate_permission`
Fordert den Aufstieg auf der Leiter von einem aktuellen Scope zu einem höherstufigen an (`current_scope`, `desired_scope`, `reason`).

- Berechnet `current_level` und `desired_level` durch Aufruf von `determine_permission_level()` auf jedem Scope.
- Gibt sofort `{"success": False}` zurück, wenn `desired_level <= current_level` (kein Downgrade erlaubt).
- Gibt andernfalls zurück: `current_level`, `desired_level`, `value_proposition` und `requires` (aus der `PERMISSION_LADDER`-Konfiguration), sowie einen `suggested_request`-String, formatiert von `format_permission_request()` (bereit zur Anzeige in einer konversationellen UI).
- **Erstellt keinen Grant** — dient nur als Planungs-/UX-Hilfsmittel; der zweite Schritt ist `confirm_permission`.

---

### `confirm_permission`
Schließt eine Eskalation ab (`current_scope`, `desired_scope`, `reason`, `duration`, optional `constraints`) — atomarer Zweischritt, der den alten Grant ablöst und den neuen erstellt.

- **Schritt 1** — widerruft den aktiven Grant für `current_scope` per Soft-Delete mit `revoked_by = "escalation"` und schreibt ein `REVOKE`-Ereignis mit `outcome = "superseded_by_escalation"`.
- **Schritt 2** — erstellt einen neuen `PermissionGrant` für `desired_scope` (gleiche Logik wie `request_permission`, inkl. Guardrails-Auto-Anhang bei Stufe 5).
- **Schritt 3** — schreibt ein `ESCALATE`-Audit-Ereignis mit vollständigem Kontext (`from_scope`, `from_level`, `to_scope`, `to_level`, `superseded_permission_id`).
- Gibt `success`, `superseded_permission_id`, `new_permission` und `escalation_summary` zurück.
- Verhindert impliziten Scope-Wildwuchs: Es wird nie ein Duplikat-Grant für denselben Scope erzeugt.

> **Bewusster Zweischritt im Sinne von Godin:** `escalate_permission` zeigt den Wertnutzen und wartet auf das explizite „Ja" des Nutzers — erst `confirm_permission` schreibt. Das Einwilligungsmoment bleibt sichtbar und auditierbar.

---

### `explain_permission`
Gibt eine für Menschen lesbare Erklärung zurück, was ein bestimmter Scope ermöglicht (`scope: str`).

- Löst den Scope über `determine_permission_level()` in sein `PermissionLadderLevel` auf.
- Gibt zurück: `scope`, `level` (int), `label`, `description`, `value_proposition`, `requires`, `example` (Anwendungsfall), `can_revoke: true` und `revocation_command` (z. B. `"'stop orders'"`).
- Gedacht für die Nutzung in Einwilligungs-UI-Texten oder agentisch generierten Erklärungen.

---

## MCP-Ressourcen

| URI | Zweck |
|-----|-------|
| `resource://permissions/{user_id}/current` | Momentaufnahme aller aktiven Grants — gibt `permission_count` (int), `highest_level` (int 0–5) und die vollständige serialisierte Grant-Liste zurück |
| `resource://permissions/{user_id}/ladder` | Vollständige `PERMISSION_LADDER`-Definition + `available_escalations`, gefiltert auf Stufen oberhalb des aktuellen Maximums des Nutzers |
| `resource://permissions/{user_id}/audit` | Die letzten 50 `AuditEvent`-Einträge (vom Ende des Protokolls) — als DSGVO-Artikel-30-konform ausgewiesen |

---

## Datenmodelle

| Modell | Rolle | Schlüsselfelder |
|--------|-------|-----------------|
| `PermissionGrant` | Zentrale persistierte Entität (ein Eintrag pro Einwilligungsakt) | `permission_id` (UUID-Präfix), `level` (1–5), `scope` (str), `granted_at`, `expires_at` (nullable), `source`, `context`, `use_count` (int), `constraints`, `guardrails`, `revoked_at` (nullable) |
| `PermissionConstraints` | Begrenzter Geltungsbereich für Stufe 5 — beim Erstellen an den Grant angehängt | `product_id`, `category_id`, `max_price_usd` (float), `max_quantity` (int), `frequency_limit` (`"daily"` / `"weekly"` / `"monthly"`), `time_windows` (Liste), `require_notification` (bool, Standard: `True`) |
| `PermissionGuardrails` | Eskalations- und Sicherheitsauslöser — automatisch bei Stufe 5 angehängt | `require_confirmation_if` (Liste von Bedingungsstrings), `auto_revoke_if` (Liste), `notify_on` (Liste) |
| `AuditEvent` | Unveränderlicher Protokolleintrag — bei jedem Werkzeugaufruf geschrieben | `event_id`, `timestamp`, `action` (`GRANT` / `CHECK` / `REVOKE` / `DENY` / `ESCALATE`), `user_id`, `agent_id`, `scope`, `level`, `outcome`, `context` (dict) |

---

## Wesentliche Gestaltungsprinzipien

- **Einwilligung ist explizit** — kein Scope oberhalb von Stufe 1 wird ohne Nutzerzustimmung angenommen (Auto-Grant-Flag ist `False` für die Stufen 2–5).
- **Werteaustausch ist sichtbar** — jede Erlaubnisanfrage zeigt einen klaren `value_proposition`-String aus der Leiterkonfiguration.
- **Widerruf ist jederzeit möglich** — das Soft-Delete-Muster bedeutet, dass `revoke_permission` niemals referenzielle Integrität verletzt; der Agent degradiert graceful.
- **Prüfpfad standardmäßig** — jeder Werkzeugaufruf fügt ein `AuditEvent` hinzu; das Protokoll wird nie abgeschnitten, nur beim Lesen in Scheiben ausgegeben.
- **Einschränkungen sind bei Stufe 5 verpflichtend** — `ValueError` wird am Anfang von `request_permission` ausgelöst, bevor irgendein Schreibvorgang stattfindet.

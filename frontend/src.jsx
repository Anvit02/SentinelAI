
import React, { useEffect, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";

import {
  Shield,
  Activity,
  Search,
  AlertTriangle,
  CheckCircle,
  ArrowRight,
  RefreshCw,
  Database,
  Clock,
} from "lucide-react";

import "./style.css";


// ============================================================
// API CONFIGURATION
// ============================================================

const API = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";


// ============================================================
// STATUS CONFIGURATION
// ============================================================

const STATUS_OPTIONS = [
  {
    value: "awaiting_human_review",
    label: "Awaiting Review",
  },
  {
    value: "in_progress",
    label: "In Progress",
  },
  {
    value: "resolved",
    label: "Resolved",
  },
  {
    value: "dismissed",
    label: "Dismissed",
  },
];


// ============================================================
// HELPER FUNCTIONS
// ============================================================

function formatText(value) {
  if (!value) return "Unknown";

  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function formatDate(value) {
  if (!value) return "Unknown";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString();
}


function severityClass(severity) {
  return severity === "low" ? "safe" : "warn";
}


// ============================================================
// MAIN APPLICATION
// ============================================================

function App() {

  // ----------------------------------------------------------
  // APPLICATION STATE
  // ----------------------------------------------------------

  const [page, setPage] = useState("overview");

  const [events, setEvents] = useState([]);

  const [investigations, setInvestigations] = useState([]);

  const [stats, setStats] = useState({
    events: 0,
    investigations: 0,
    critical_investigations: 0,
  });

  const [selected, setSelected] = useState(null);

  const [report, setReport] = useState(null);

  const [error, setError] = useState("");

  const [busy, setBusy] = useState(false);

  const [loading, setLoading] = useState(true);

  const [refreshing, setRefreshing] = useState(false);


  // ==========================================================
  // API REQUEST HELPER
  // ==========================================================

  const getJSON = useCallback(async (path, options = {}) => {

    let response;

    try {
      response = await fetch(API + path, options);
    } catch {
      throw new Error(
        "Unable to connect to FastAPI. " +
        "Check that the backend is running and reachable."
      );
    }

    if (!response.ok) {

      let message = `Request failed (${response.status})`;

      try {
        const data = await response.json();

        if (typeof data.detail === "string") {
          message = data.detail;
        }
      } catch {
        // Keep the HTTP error message.
      }

      throw new Error(message);
    }

    return response.json();

  }, []);


  // ==========================================================
  // LOAD DASHBOARD DATA
  // ==========================================================

  const loadDashboard = useCallback(async () => {

    const [
      eventData,
      investigationData,
      statsData,
    ] = await Promise.all([

      getJSON("/api/events"),

      getJSON("/api/investigations"),

      getJSON("/api/stats"),

    ]);

    setEvents(eventData);

    setInvestigations(investigationData);

    setStats(statsData);

  }, [getJSON]);


  // ==========================================================
  // INITIAL DATA LOADING
  // ==========================================================

  useEffect(() => {

    let active = true;

    async function initialize() {

      try {

        const [
          eventData,
          investigationData,
          statsData,
        ] = await Promise.all([

          getJSON("/api/events"),

          getJSON("/api/investigations"),

          getJSON("/api/stats"),

        ]);

        if (!active) return;

        setEvents(eventData);

        setInvestigations(investigationData);

        setStats(statsData);

        setError("");

      } catch (err) {

        if (active) {
          setError(err.message);
        }

      } finally {

        if (active) {
          setLoading(false);
        }

      }

    }

    initialize();

    return () => {
      active = false;
    };

  }, [getJSON]);


  // ==========================================================
  // REFRESH DATA
  // ==========================================================

  async function refreshData() {

    if (refreshing || busy) return;

    setRefreshing(true);

    setError("");

    try {

      await loadDashboard();

    } catch (err) {

      setError(err.message);

    } finally {

      setRefreshing(false);

    }

  }


  // ==========================================================
  // RUN INVESTIGATION
  // ==========================================================

  async function investigate(event) {

    if (busy) return;

    setBusy(true);

    setError("");

    setSelected(event);

    setReport(null);

    try {

      const data = await getJSON(
        "/api/investigations/" + encodeURIComponent(event.id),
        {
          method: "POST",
        }
      );

      setReport(data);

      await loadDashboard();

      setPage("overview");

    } catch (err) {

      setError(err.message);

    } finally {

      setBusy(false);

    }

  }


  // ==========================================================
  // OPEN INVESTIGATIONS PAGE
  // ==========================================================

  async function openInvestigations() {

    setPage("investigations");

    setError("");

    try {

      const data = await getJSON("/api/investigations");

      setInvestigations(data);

    } catch (err) {

      setError(err.message);

    }

  }


  // ==========================================================
  // VIEW SAVED INVESTIGATION REPORT
  // ==========================================================

  async function viewReport(item) {

    if (busy) return;

    setBusy(true);

    setError("");

    try {

      // Fetch the saved report using its investigation ID.
      // This does NOT create another investigation.

      const data = await getJSON(
        "/api/investigations/" + encodeURIComponent(item.id)
      );

      setReport(data);

      const event = events.find(
        (e) => e.id === data.event_id
      );

      setSelected(event || null);

      setPage("overview");

    } catch (err) {

      setError(err.message);

    } finally {

      setBusy(false);

    }

  }


  // ==========================================================
  // UPDATE INVESTIGATION STATUS
  // ==========================================================

  async function updateStatus(item, status) {

    if (busy) return;

    setBusy(true);

    setError("");

    try {

      const updated = await getJSON(
        "/api/investigations/" + encodeURIComponent(item.id),
        {
          method: "PATCH",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            status: status,
          }),
        }
      );

      // Update the visible report if it is the same record.

      setReport((current) => {

        if (current && current.id === updated.id) {
          return updated;
        }

        return current;

      });

      await loadDashboard();

    } catch (err) {

      setError(err.message);

    } finally {

      setBusy(false);

    }

  }


  // ==========================================================
  // DASHBOARD STATISTICS
  // ==========================================================

  const totalEvents = stats.events ?? events.length;

  const totalInvestigations =
    stats.investigations ?? investigations.length;

  const criticalInvestigations =
    stats.critical_investigations ??
    investigations.filter(
      (item) => item.severity === "critical"
    ).length;


  // ==========================================================
  // APPLICATION UI
  // ==========================================================

  return (

    <div className="shell">

      {/* ====================================================
          SIDEBAR
      ==================================================== */}

      <aside>

        <div className="brand">

          <Shield size={25} />

          SENTINEL<span>AI</span>

        </div>


        <div className="sideLabel">
          WORKSPACE
        </div>


        <button type="button"
          className={
            "nav " +
            (page === "overview" ? "active" : "")
          }
          onClick={() => setPage("overview")}
        >

          <Activity size={18} />

          Security Overview

        </button>


        <button type="button"
          className={
            "nav " +
            (page === "investigations" ? "active" : "")
          }
          onClick={openInvestigations}
        >

          <Search size={18} />

          Investigations

        </button>


        <div className="sideBottom">

          PROTOTYPE v0.3

          <br />

          Synthetic data only

        </div>

      </aside>


      {/* ====================================================
          MAIN CONTENT
      ==================================================== */}

      <main>

        {/* --------------------------------------------------
            PAGE HEADER
        -------------------------------------------------- */}

        <header>

          <div>

            <div className="eyebrow">

              SECURITY OPERATIONS / {page.toUpperCase()}

            </div>


            <h1>

              {page === "overview"
                ? "Threat Intelligence Dashboard"
                : "Security Investigations"}

            </h1>


            <p>

              {page === "overview"
                ? "Investigate suspicious events with evidence-backed risk analysis."
                : "Review investigation history and manage analyst workflows."}

            </p>

          </div>


          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >

            <button
              type="button"
              onClick={refreshData}
              disabled={refreshing || busy}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "7px",
              }}
            >

              <RefreshCw size={15} />

              {refreshing ? "Refreshing..." : "Refresh Data"}

            </button>


            <div className="live">

              <span className="dot" />

              Local simulation

            </div>

          </div>

        </header>


        {/* --------------------------------------------------
            ERROR MESSAGE
        -------------------------------------------------- */}

        {error && (

          <div className="error" role="alert">

            <AlertTriangle size={17} />

            <span>{error}</span>

          </div>

        )}


        {/* --------------------------------------------------
            INITIAL LOADING
        -------------------------------------------------- */}

        {loading ? (

          <section>

            <div className="empty">

              <RefreshCw size={28} />

              <p>Loading SentinelAI dashboard...</p>

            </div>

          </section>

        ) : page === "overview" ? (

          <>

            {/* ==============================================
                DASHBOARD STATISTICS
            ============================================== */}

            <div className="stats">

              <div className="stat">

                <small>

                  <Database size={13} />

                  {" "}EVENTS INGESTED

                </small>

                <strong>{totalEvents}</strong>

                <span>
                  Stored security telemetry
                </span>

              </div>


              <div className="stat">

                <small>

                  <AlertTriangle size={13} />

                  {" "}CRITICAL INVESTIGATIONS

                </small>

                <strong>{criticalInvestigations}</strong>

                <span>
                  High-priority analyst review
                </span>

              </div>


              <div className="stat">

                <small>

                  <Search size={13} />

                  {" "}INVESTIGATIONS

                </small>

                <strong>{totalInvestigations}</strong>

                <span>
                  Saved investigation records
                </span>

              </div>

            </div>


            {/* ==============================================
                SECURITY EVENT STREAM
            ============================================== */}

            <section>

              <div className="sectionHead">

                <div>

                  <h2>Security event stream</h2>

                  <p>
                    Select an event to run the investigation engine.
                  </p>

                </div>


                <span className="pill">
                  LIVE DEMO DATA
                </span>

              </div>


              <div className="tableWrap">

                <table>

                  <thead>

                    <tr>

                      <th>EVENT</th>

                      <th>USER</th>

                      <th>IP ADDRESS</th>

                      <th>TYPE</th>

                      <th>ACTION</th>

                    </tr>

                  </thead>


                  <tbody>

                    {events.map((event) => (

                      <tr key={event.id}>

                        <td className="mono">
                          {event.id}
                        </td>


                        <td>
                          {event.user}
                        </td>


                        <td className="mono">
                          {event.ip}
                        </td>


                        <td>

                          <span
                            className={
                              "tag " +
                              (event.type === "normal_login"
                                ? "safe"
                                : "warn")
                            }
                          >

                            {formatText(event.type)}

                          </span>

                        </td>


                        <td>

                          <button
                            type="button"
                            onClick={() => investigate(event)}
                            disabled={busy || refreshing}
                          >

                            Investigate

                            <ArrowRight size={14} />

                          </button>

                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

              </div>


              {events.length === 0 && (

                <div className="empty">

                  No security events available.

                </div>

              )}

            </section>


            {/* ==============================================
                INVESTIGATION REPORT
            ============================================== */}

            <section className="investigation">

              <div className="sectionHead">

                <div>

                  <h2>Investigation report</h2>

                  <p>
                    Evidence, scoring and recommended analyst response.
                  </p>

                </div>

              </div>


              {busy ? (

                <div className="empty">

                  <RefreshCw size={28} />

                  <p>Loading investigation...</p>

                </div>

              ) : report ? (

                <>

                  {/* ----------------------------------------
                      REPORT HEADER
                  ---------------------------------------- */}

                  <div className="reportTop">

                    <div>

                      <small>
                        EVENT {report.event_id}
                      </small>


                      <h3>
                        {report.summary}
                      </h3>


                      <span
                        className={
                          "tag " +
                          severityClass(report.severity)
                        }
                      >

                        {formatText(report.severity)}

                      </span>


                      <p
                        style={{
                          marginTop: "12px",
                          fontSize: "13px",
                          opacity: 0.75,
                        }}
                      >

                        Investigation ID: {report.id}

                      </p>


                      <p
                        style={{
                          marginTop: "6px",
                          fontSize: "13px",
                          opacity: 0.75,
                        }}
                      >

                        <Clock
                          size={13}
                          style={{
                            display: "inline",
                            verticalAlign: "middle",
                          }}
                        />

                        {" "}Created: {formatDate(report.created_at)}

                      </p>


                      <p
                        style={{
                          marginTop: "6px",
                          fontSize: "13px",
                          opacity: 0.75,
                        }}
                      >

                        Status: {formatText(report.status)}

                      </p>

                    </div>


                    <div className="risk">

                      <strong>

                        {report.risk_score}

                        <span>/100</span>

                      </strong>


                      <small>
                        RULE-BASED RISK SCORE
                      </small>

                    </div>

                  </div>


                  {/* ----------------------------------------
                      REPORT DETAILS
                  ---------------------------------------- */}

                  {report.authentication_analysis && (
                    <section className="reportTop" aria-label="Authentication model">
                      <div>
                        <h4>Authentication model</h4>
                        <p>
                          {report.authentication_analysis.flagged ? "Flagged" : "Not flagged"}
                          {" · "}
                          {Math.round(report.authentication_analysis.suspicion_score * 100)}% synthetic suspicion score
                        </p>
                        <p>Trained on synthetic retry counts. Analyst review required.</p>
                      </div>
                    </section>
                  )}

                  {report.anomaly_analysis && (
                    <section className="reportTop" aria-label="Anomaly detection">
                      <div>
                        <h4>Anomaly detection</h4>
                        <p>
                          {report.anomaly_analysis.flagged ? "Unusual activity" : "Within baseline"}
                          {" · Isolation Forest score "}
                          {report.anomaly_analysis.anomaly_score.toFixed(4)}
                          {" · Threshold "}
                          {report.anomaly_analysis.threshold.toFixed(4)}
                        </p>
                        <p>
                          {report.anomaly_analysis.features.failed_logins} failed login attempts in this event
                          {" · "}
                          {report.anomaly_analysis.features.recent_failure_events} failure events for this account in 15 minutes
                        </p>
                      </div>
                    </section>
                  )}

                  <div className="reportGrid">

                    {/* EVIDENCE */}

                    <div>

                      <h4>Evidence signals</h4>


                      {report.evidence?.length ? (

                        report.evidence.map((evidence, index) => (

                          <div
                            className="evidence"
                            key={index}
                          >

                            <AlertTriangle size={16} />

                            <div>

                              <b>

                                {evidence.signal}

                                {" "}

                                <span>
                                  +{evidence.points}
                                </span>

                              </b>


                              <p>
                                {evidence.detail}
                              </p>

                            </div>

                          </div>

                        ))

                      ) : (

                        <div className="evidence">

                          <CheckCircle size={16} />

                          No suspicious signals detected.

                        </div>

                      )}

                    </div>


                    {/* RECOMMENDED ACTIONS */}

                    <div>

                      <h4>
                        Recommended actions · Human approval required
                      </h4>


                      {report.recommended_actions?.map(
                        (action, index) => (

                          <div
                            className="action"
                            key={index}
                          >

                            {index + 1}. {action}

                          </div>

                        )
                      )}


                      <p className="notice">

                        No response actions are automatically executed.

                        Scores are not calibrated probabilities.

                      </p>

                    </div>

                  </div>


                  {/* ----------------------------------------
                      SCORING INFORMATION
                  ---------------------------------------- */}

                  <div
                    style={{
                      marginTop: "18px",
                      fontSize: "12px",
                      opacity: 0.7,
                    }}
                  >

                    Scoring method: {report.scoring_method}

                  </div>

                </>

              ) : (

                <div className="empty">

                  <Shield size={34} />

                  <p>

                    Choose an event and click{" "}

                    <b>Investigate</b>

                    {" "}to generate a report.

                  </p>

                </div>

              )}

            </section>

          </>

        ) : (

          /* =================================================
             INVESTIGATION HISTORY PAGE
          ================================================= */

          <section>

            <div className="sectionHead">

              <div>

                <h2>Investigation History</h2>

                <p>
                  Previously generated security investigations.
                </p>

              </div>


              <span className="pill">

                {totalInvestigations} RECORDS

              </span>

            </div>


            <div className="tableWrap">

              <table>

                <thead>

                  <tr>

                    <th>EVENT</th>

                    <th>SEVERITY</th>

                    <th>RISK SCORE</th>

                    <th>STATUS</th>

                    <th>ACTIONS</th>

                  </tr>

                </thead>


                <tbody>

                  {investigations.map((item) => (

                    <tr key={item.id}>

                      <td className="mono">

                        {item.event_id}

                      </td>


                      <td>

                        <span
                          className={
                            "tag " +
                            severityClass(item.severity)
                          }
                        >

                          {formatText(item.severity)}

                        </span>

                      </td>


                      <td>

                        {item.risk_score}/100

                      </td>


                      <td>

                        <select
                          value={item.status}
                          disabled={busy || refreshing}
                          onChange={(e) =>
                            updateStatus(item, e.target.value)
                          }
                        >

                          {STATUS_OPTIONS.map((option) => (

                            <option
                              key={option.value}
                              value={option.value}
                            >

                              {option.label}

                            </option>

                          ))}

                        </select>

                      </td>


                      <td>

                        <button
                          type="button"
                          onClick={() => viewReport(item)}
                          disabled={busy || refreshing}
                        >

                          View Report

                          <ArrowRight size={14} />

                        </button>

                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>


            {investigations.length === 0 && (

              <div className="empty">

                <Search size={30} />

                <p>

                  No investigations yet.

                  Investigate an event to get started.

                </p>

              </div>

            )}

          </section>

        )}

      </main>

    </div>

  );

}


// ============================================================
// REACT APPLICATION ENTRY POINT
// ============================================================

createRoot(
  document.getElementById("root")
).render(
  <App />
);

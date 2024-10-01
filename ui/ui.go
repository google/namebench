// Package ui The ui package contains methods for handling UI URL's.
package ui

import (
	"github.com/Cellularhacker/apiError-go"
	"github.com/Cellularhacker/apiHandler-gin-go"
	"github.com/Cellularhacker/logger-go"
	"html/template"
	"namebench/model/namebench/record"
	"namebench/service/dnschecks"
	"namebench/service/dnsqueue"
	"namebench/service/history"
	"net/http"
	"strconv"
	"strings"
)

const (
	// QueueLength How many requests/responses can be queued at once
	QueueLength = 65535

	// WORKERS Number of workers (same as Chrome's DNS prefetch queue)
	WORKERS = 8

	// COUNT Number of tests to run
	COUNT = 50

	// HistoryDays How far back to reach into browser history
	HistoryDays = 90

	FilterAll        = 0
	FilterNonISPOnly = 1
	FilterISPOnly    = 2
)

var (
	indexTmpl = loadTemplate("ui/templates/index.html")
)

// RegisterHandlers registers all known handlers.
func RegisterHandlers() {
	http.HandleFunc("/", Index)
	http.Handle("/static/", http.StripPrefix("/static", http.FileServer(http.Dir("ui/static"))))
	http.HandleFunc("/submit", Submit)
	http.HandleFunc("/dnssec", DnsSec)
	http.HandleFunc("/submit_and_run", SubmitAndRun)
}

// loadTemplate loads a set of templates.
func loadTemplate(paths ...string) *template.Template {
	t := template.New(strings.Join(paths, ","))
	_, err := t.ParseFiles(paths...)
	if err != nil {
		panic(err)
	}
	return t
}

// Index handles /
func Index(w http.ResponseWriter, _ *http.Request) {
	if err := indexTmpl.ExecuteTemplate(w, "index.html", nil); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// DnsSec handles /dnssec
func DnsSec(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	qFilter, err := strconv.Atoi(q.Get("filter"))
	if err != nil || qFilter < 0 || qFilter > 2 {
		apiHandler.ErrorHandler(w, r, apiError.BadRequestError("filter"))
		return
	}
	result := DoDnsSec(qFilter)

	apiHandler.JSONHandler(w, r, *result, nil, http.StatusOK)
}

func DoDnsSec(filter int, records ...*record.Record) *dnschecks.CheckResults {
	dss := dnschecks.DnsServers
	crs := make([]dnschecks.CheckResult, 0)

	for i := range dss {
		ds := dss[i]
		if filter == FilterISPOnly && !ds.IsISP {
			continue
		}
		if filter == FilterNonISPOnly && ds.IsISP {
			continue
		}

		cr, err := dnschecks.DnsSec(ds, records...)
		if err != nil {
			logger.L.Errorf("%s DNSSEC: %t, took: %s (%s)", cr.DnsServer.Address(), cr.DnsSec, cr.Timer.Took.String(), err)
		} else {
			logger.L.Infof("%s DNSSEC: %t, took: %s", cr.DnsServer.Address(), cr.DnsSec, cr.Timer.Took.String())
		}

		crs = append(crs, *cr)
	}

	result := dnschecks.CheckResults(crs)
	result.Sort()

	return &result
}

// Submit handles /submit
func Submit(w http.ResponseWriter, r *http.Request) {
	drs, err := DoSubmit()
	if err != nil {
		apiHandler.ErrorHandler(w, r, apiError.InternalServerError(err))
		return
	}

	apiHandler.JSONHandler(w, r, drs, nil, http.StatusOK)
}

func DoSubmit() (*dnsqueue.Results, error) {
	records, err := history.Chrome(HistoryDays)
	if err != nil {
		logger.L.Errorln("history2.Chrome(HistoryDays)", err)
		return nil, err
	}

	q := dnsqueue.StartQueue(QueueLength, WORKERS)
	extHostnames := history.ExternalHostnames(records)
	extUniqHostnames := history.Uniq(extHostnames)
	hostnames := history.Random(COUNT, extUniqHostnames)

	for _, hostname := range hostnames {
		q.Add("8.8.8.8:53", "A", hostname+".")
		//logger.L.Infof("Added %s", hostname)
	}
	q.SendCompletionSignal()

	result := make([]dnsqueue.Result, 0)
	for answered := 0; answered < len(hostnames); answered++ {
		cResult := <-q.Results
		//logger.L.Infof("cResult => %s", cResult)
		if cResult.Error != nil {
			continue
		}

		result = append(result, *cResult)
	}
	resp := dnsqueue.Results(result)
	return &resp, nil
}

type SubmitAndRunData struct {
	Record  *record.Record          `json:"record,omitempty"`
	Results *dnschecks.CheckResults `json:"results,omitempty"`
}

// SubmitAndRun handles /submit_and_run
func SubmitAndRun(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	qFilter, err := strconv.Atoi(q.Get("filter"))
	if err != nil || qFilter < 0 || qFilter > 2 {
		apiHandler.ErrorHandler(w, r, apiError.BadRequestError("filter"))
		return
	}
	dataType := q.Get("data_type")
	if dataType != "" && dataType != "array" && dataType != "map" {
		apiHandler.ErrorHandler(w, r, apiError.BadRequestError("data_type"))
		return
	}

	drs, err := DoSubmit()
	if err != nil {
		apiHandler.ErrorHandler(w, r, apiError.InternalServerError(err))
		return
	}

	records := drs.ExtractRecords()

	sards := make([]SubmitAndRunData, 0)
	for _, rec := range *records {
		checkResults := DoDnsSec(qFilter, &rec)

		cResult := &SubmitAndRunData{
			Record:  &rec,
			Results: checkResults,
		}

		sards = append(sards, *cResult)
	}

	if dataType == "map" {
		resultMap := make(map[string]SubmitAndRunData)
		for _, sard := range sards {
			resultMap[sard.Record.Name] = sard
		}
		apiHandler.JSONHandler(w, r, resultMap, nil, http.StatusOK)
		return
	}
	apiHandler.JSONHandler(w, r, sards, nil, http.StatusOK)
}

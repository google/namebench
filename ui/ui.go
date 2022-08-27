// Package ui The ui package contains methods for handling UI URL's.
package ui

import (
	"html/template"
	"namebench/dnschecks"
	"namebench/dnsqueue"
	"namebench/history"
	"namebench/util/logger"
	"net/http"
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
	HistoryDays = 30
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
func Index(w http.ResponseWriter, r *http.Request) {
	if err := indexTmpl.ExecuteTemplate(w, "index.html", nil); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
	return
}

// DnsSec handles /dnssec
func DnsSec(w http.ResponseWriter, r *http.Request) {
	servers := []string{
		"8.8.8.8:53",
		"75.75.75.75:53",
		"4.2.2.1:53",
		"208.67.222.222:53",
	}
	for _, ip := range servers {
		result, err := dnschecks.DnsSec(ip)
		logger.L.Infof("%s DNSSEC: %s (%s)", ip, result, err)
	}
}

// Submit handles /submit
func Submit(w http.ResponseWriter, r *http.Request) {
	records, err := history.Chrome(HistoryDays)
	if err != nil {
		panic(err)
	}

	q := dnsqueue.StartQueue(QueueLength, WORKERS)
	hostnames := history.Random(COUNT, history.Uniq(history.ExternalHostnames(records)))

	for _, record := range hostnames {
		q.Add("8.8.8.8:53", "A", record+".")
		logger.L.Infof("Added %s", record)
	}
	q.SendCompletionSignal()
	answered := 0
	for {
		if answered == len(hostnames) {
			break
		}
		result := <-q.Results
		answered += 1
		logger.L.Infof("%s", result)
	}
	return
}

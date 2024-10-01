// Package history the history package is a collection of functions for reading history files from browsers.
package history

import (
	"database/sql"
	"fmt"
	"github.com/Cellularhacker/logger-go"
	_ "github.com/mattn/go-sqlite3"
	"io"
	"os"
	"sync"
)

type chromePaths struct {
	urls []string
	m    *sync.Mutex
}

func (cps *chromePaths) Append(path string) {
	cps.m.Lock()
	cps.urls = append(cps.urls, path)
	cps.m.Unlock()
}

func (cps *chromePaths) Get() []string {
	return cps.urls
}

func NewChromePaths() *chromePaths {
	return &chromePaths{
		urls: make([]string, 0),
		m:    &sync.Mutex{},
	}
}

// unlockDatabase is a bad hack for opening potentially locked SQLite databases.
func unlockDatabase(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	t, err := os.CreateTemp("", "")
	if err != nil {
		return "", err
	}
	defer t.Close()

	written, err := io.Copy(t, f)
	if err != nil {
		return "", err
	}
	logger.L.Infof("%d bytes written to %s", written, t.Name())
	return t.Name(), err
}

// Chrome returns an array of URLs found in Chrome's history within X days
func Chrome(days int) ([]string, error) {
	paths := []string{
		"${HOME}/Library/Application Support/Google/Chrome/Default/History",
		"${HOME}/.config/google-chrome/Default/History",
		"${APPDATA}/Google/Chrome/User Data/Default/History",
		"${USERPROFILE}/Local Settings/Application Data/Google/Chrome/User Data/Default/History",
	}

	cps := NewChromePaths()
	query := fmt.Sprintf(
		`SELECT urls.url FROM visits
		 LEFT JOIN urls ON visits.url = urls.id
		 WHERE (visit_time - 11644473600000000 >
			    strftime('%%s', date('now', '-%d day')) * 1000000)
		 ORDER BY visit_time DESC`, days)

	for _, p := range paths {
		findAndAppendPath(p, query, cps)
	}
	return cps.Get(), nil
}

func findAndAppendPath(cPath string, query string, cps *chromePaths) {
	p := os.ExpandEnv(cPath)
	logger.L.Infof("Checking %s", cPath)
	_, err := os.Stat(p)
	if err != nil {
		logger.L.Errorln("os.Stat(p)", err)
		return
	}

	unlockedPath, err := unlockDatabase(p)
	if err != nil {
		logger.L.Errorln("unlockDatabase(p)", err)
		return
	}
	defer os.Remove(unlockedPath)

	db, err := sql.Open("sqlite3", unlockedPath)
	if err != nil {
		logger.L.Errorln(`sql.Open("sqlite3", unlockedPath)`, err)
		return
	}

	rows, err := db.Query(query)
	if err != nil {
		logger.L.Errorf("Query failed: %s", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		url := ""
		if err2 := rows.Scan(&url); err2 != nil {
			continue
		}
		cps.Append(url)
	}
}

// the history package is a collection of functions for reading history files from browsers.
package history

import (
	"database/sql"
	"fmt"
	_ "github.com/mattn/go-sqlite3"
	"io"
	"io/ioutil"
	"log"
	"os"
)

// unlockAndOpen is a bad hack for opening potentially locked SQLite databases.
func unlockAndOpenDatabase(path string) (db *sql.DB, err error) {
	f, err := os.Open(path)
	defer f.Close()
	if err != nil {
		return nil, err
	}

	t, err := ioutil.TempFile("", "")
	io.Copy(t, f)
	t.Close()
	defer os.Remove(t.Name())

	log.Printf("Opening %s", t.Name())
	return sql.Open("sqlite3", t.Name())
}

// Chrome returns an array of URLs found in Chrome's history within X days, limited by Y.
func Chrome(days, limit int) (urls []string, err error) {
	paths := []string{
		"${HOME}/Library/Application Support/Google/Chrome/Default/History",
		"${HOME}/.config/google-chrome/Default/History",
		"${APPDATA}/Google/Chrome/User Data/Default/History",
		"${USERPROFILE}/Local Settings/Application Data/Google/Chrome/User Data/Default/History",
	}

	query := fmt.Sprintf(
		`SELECT urls.url FROM visits
		 LEFT JOIN urls ON visits.url = urls.id
		 WHERE (visit_time - 11644473600000000 >
			    strftime('%%s', date('now', '-%d day')) * 1000000)
		 ORDER BY RANDOM()
		 LIMIT %d;`, days, limit)

	for _, p := range paths {
		path := os.ExpandEnv(p)
		log.Printf("Checking %s", path)
		_, err := os.Stat(path)
		if err == nil {
			db, err := unlockAndOpenDatabase(path)
			if err != nil {
				return nil, err
			}
			db.Query("PRAGMA query_only = true;")
			db.Query("PRAGMA read_uncommitted = true;")
			log.Printf("%s", query)
			rows, err := db.Query(query)
			if err != nil {
				log.Printf("Query failed: %s", err)
				return nil, err
			}
			var url string
			for rows.Next() {
				rows.Scan(&url)
				urls = append(urls, url)
			}
			rows.Close()
			return urls, err
		}
	}
	return
}

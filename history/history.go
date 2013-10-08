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

// unlockDatabase is a bad hack for opening potentially locked SQLite databases.
func unlockDatabase(path string) (unlocked_path string, err error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	t, err := ioutil.TempFile("", "")
	if err != nil {
		return "", err
	}
	defer t.Close()

	written, err := io.Copy(t, f)
	if err != nil {
		return "", err
	}
	log.Printf("%d bytes written to %s", written, t.Name())
	return t.Name(), err
}

// Chrome returns an array of URLs found in Chrome's history within X days
func Chrome(days int) (urls []string, err error) {
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
		 ORDER BY visit_time DESC`, days)

	for _, p := range paths {
		path := os.ExpandEnv(p)
		log.Printf("Checking %s", path)
		_, err := os.Stat(path)
		if err != nil {
			continue
		}

		unlocked_path, err := unlockDatabase(path)
		if err != nil {
			return nil, err
		}
		defer os.Remove(unlocked_path)

		db, err := sql.Open("sqlite3", unlocked_path)
		if err != nil {
			return nil, err
		}

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
	return
}

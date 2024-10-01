package record

var Default = &Record{Type: "A", Name: "www.dnssec-failed.org."}

func Unique(records []Record) []Record {
	result := make([]Record, 0)
	rHostnameMap := make(map[string]bool)

	for _, r := range records {
		n := r.Name
		if _, e := rHostnameMap[n]; e {
			continue
		}

		rHostnameMap[n] = true
		result = append(result, r)
	}

	return result
}

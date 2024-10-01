// Package history part of the history package, provides filtering capabilities.
package history

import (
	"github.com/Cellularhacker/logger-go"
	"golang.org/x/net/publicsuffix"
	"math/rand"
	"net/url"
	"regexp"
)

var (
	internalRe = regexp.MustCompile(`\.corp|\.sandbox\.|\.borg\.|\.hot\.|internal|dmz|\._[ut][dc]p\.|intra|\.\w$|\.\w{5,}$`)
)

func isPossiblyInternal(addr string) bool {
	// note: this happens to reject IPs and anything with a port at the end.
	_, icann := publicsuffix.PublicSuffix(addr)
	if !icann {
		logger.L.Errorf("%s does not have a public suffix", addr)
		return true
	}
	if internalRe.MatchString(addr) {
		logger.L.Warnf("%s may be internal.", addr)
		return true
	}
	return false
}

// ExternalHostnames Filter out external hostnames from history
func ExternalHostnames(entries []string) []string {
	counter := 0
	hostnames := make([]string, 0)

	for _, uString := range entries {
		u, err := url.ParseRequestURI(uString)
		if err != nil {
			logger.L.Errorf("Error parsing %s: %s", uString, err)
			continue
		}
		if !isPossiblyInternal(u.Hostname()) {
			counter += 1
			hostnames = append(hostnames, u.Hostname())
		}
	}

	return hostnames
}

// Uniq Filter input array for unique entries.
func Uniq(input []string) []string {
	inputMap := make(map[string]bool)
	result := make([]string, 0)

	for _, v := range input {
		if _, e := inputMap[v]; !e {
			result = append(result, v)
			inputMap[v] = true
		}
	}
	return result
}

// Random Randomly select X number of entries.
func Random(count int, input []string) []string {
	if count >= len(input) {
		return input
	}

	selected := make(map[int]bool)
	result := make([]string, 0)

	for i := 0; len(selected) < count && i < len(input); i++ {
		if len(selected) >= count {
			break
		}
		idx := rand.Intn(len(input))
		// If we have already picked this number, re-roll.
		if _, e := selected[idx]; e == true {
			continue
		}
		result = append(result, input[idx])
		selected[idx] = true
	}

	return result
}

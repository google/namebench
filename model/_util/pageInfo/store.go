package pageInfo

import (
	"net/http"
	"strconv"
)

var (
	QueryCurrentPage = "current_page"
	QueryPageSize    = "page_size"
)

func (p *Request) ToPagingInfo(totalCount int64) *Response {
	if totalCount == -1 {
		return nil
	}
	if p == nil {
		return nil
	}
	return &Response{
		TotalPage:   (totalCount-1)/p.Size + 1,
		TotalCount:  totalCount,
		CurrentPage: p.Current,
		PageSize:    p.Size,
	}
}

func ParsePageInfo(r *http.Request) (*Request, *string) {
	//Preparing variables...
	q := r.URL.Query()

	// Query - current_page
	currentPage, err := strconv.ParseInt(q.Get(QueryCurrentPage), 10, 64)
	if err != nil || currentPage <= 0 {
		return nil, &QueryCurrentPage
	}

	// Query - page_size
	pageSize, err := strconv.ParseInt(q.Get(QueryPageSize), 10, 64)
	if err != nil || pageSize < 0 {
		return nil, &QueryPageSize
	}

	return &Request{Current: currentPage, Size: pageSize, Skip: pageSize * (currentPage - 1)}, nil
}

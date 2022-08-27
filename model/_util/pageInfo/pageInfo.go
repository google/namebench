package pageInfo

type Request struct {
	Current int64 `json:"current_page"`
	Size    int64 `json:"page_size"`
	Skip    int64 `json:"skip"`
}

type Response struct {
	TotalPage   int64 `json:"total_page"`
	TotalCount  int64 `json:"total_count"`
	CurrentPage int64 `json:"current_page"`
	PageSize    int64 `json:"page_size"`
}

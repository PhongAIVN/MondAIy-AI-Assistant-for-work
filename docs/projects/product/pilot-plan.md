# Pilot plan — Program Navigator vertical

| Thuộc tính | Giá trị |
| --- | --- |
| Status | In review |
| Owner | Thái Hoài An (PM) |
| Reviewers | Mentor/Admin, Tech Lead, QA Lead |
| Last updated | 2026-08-02 |
| Related | [PRD](prd.md) · [Roadmap](roadmap-6-weeks.md) · [Evaluation](../qa/evaluation-plan.md) |

## 1. Mục tiêu

Kiểm chứng Personal Context Engine tạo ra giá trị thật qua Program Navigator:

- User không phải mở và chép lại dữ liệu từ từng nguồn kết nối.
- Brief giúp user biết điều quan trọng.
- Ask trả lời có nguồn và biết abstain.
- Memory cải thiện relevance nhưng không biến inference thành truth.
- Action Draft giảm thao tác mà vẫn an toàn.

## 2. Phạm vi

- Một cohort.
- 5–10 learners.
- Một mentor/admin làm quality escalation DRI.
- Bảy ngày liên tục.
- Timezone mặc định `Asia/Ho_Chi_Minh`.
- Calendar, Jira, Discord, VLearn và Gmail ở chế độ chỉ đọc; chỉ bật connector đạt gate.
- Calendar template/ICS, không yêu cầu OAuth.

## 3. Recruitment criteria

Tester:

- Đang tham gia cohort có deadline thật.
- Dùng trình duyệt desktop hiện đại.
- Có ít nhất ba ngày hoạt động trong tuần pilot.
- Đồng ý kết nối các nguồn được liệt kê.
- Hiểu cách disconnect/revoke/delete.

Không theo dõi màn hình, lịch sử duyệt web hoặc nội dung cuộc họp của tester.

## 4. Pre-pilot checklist

- [ ] Consent copy và phạm vi quyền từng connector được review.
- [ ] Program Frame/source authority seed xong.
- [ ] Fixture và fallback cho nguồn lỗi hoạt động.
- [ ] Full connector → Brief → Ask → Act E2E pass.
- [ ] Golden set/release thresholds pass.
- [ ] Source health, queue lag, provider cost/latency observable.
- [ ] Permission/revoke/delete tests pass.
- [ ] Incident/rollback DRI trực.
- [ ] Demo backup bằng fixture/recording.
- [ ] Không còn Sev-0/1.

## 5. Daily protocol

### User

1. Mở Brief.
2. Dùng `Hỏi` ít nhất khi có câu hỏi thật.
3. Mở citation khi cần kiểm chứng.
4. Confirm/reject memory candidate khi xuất hiện.
5. Tạo action nếu phù hợp.
6. Feedback helpful/incorrect/missing source.

### Team

1. Kiểm tra source health/queue/provider.
2. Chạy golden regression.
3. Review all incorrect/missing-source/permission failures.
4. Adjudicate failure và thêm regression fixture.
5. Chỉ deploy P0/regression fix.
6. Ghi version/model/prompt/retrieval mỗi deploy.

## 6. Metrics

Trust blockers:

- Citation coverage/correctness 100%.
- Canonical memory evidence coverage 100%.
- Unsupported deadline/assignee 0.
- Inferred-as-confirmed 0.
- Unsafe action 0.
- Cross-user leak 0.
- Event loss/duplicate 0 trong controlled suites.

Directional product metrics:

- ≥70% user đọc Brief ít nhất 4/7 ngày.
- ≥70% reviewed answers helpful.
- ≥30% user confirm ít nhất một action.
- ≥60% user nói giảm tìm/kiểm tra/nhập lại.
- Tỷ lệ hoàn thành công việc trong tuần tăng so với baseline trước pilot.

## 7. Interview questions

Trước pilot:

- Bạn thường phải tìm/giải thích/nhập lại context ở đâu?
- Nguồn nào bạn sẵn sàng kết nối ở chế độ chỉ đọc?
- Điều gì khiến bạn không tin một memory/answer?

Sau pilot:

- Khi nào Brief khiến bạn không cần mở lại nguồn?
- Có memory nào đúng nhưng khiến bạn khó chịu vì cách suy ra không?
- Citation nào không đủ để bạn tin?
- Bạn đã bỏ qua recommendation/action nào và vì sao?
- Calendar/Jira/Discord/VLearn/Gmail: nguồn nào tạo giá trị lớn nhất?
- Bạn có muốn tiếp tục dùng sau cohort không?

## 8. Exit decision

### Proceed P1

Trust blockers = 0, tỷ lệ hoàn thành công việc tăng và có evidence user value. Chọn tối đa một expansion: connector mới, Calendar write hoặc broader personal routines.

### Iterate

Trust pass nhưng behavior yếu. Sửa Brief relevance/onboarding/action value trước thêm connector.

### Stop/pivot

User vẫn phải kiểm tra mọi nguồn, không chấp nhận connector/memory, hoặc provenance không đạt dù scope bounded.

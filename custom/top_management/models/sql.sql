SELECT assembly
    sum(topic.num_votes_plus)
    sum(topic.num_votes_minus)
    sum(topic.num_votes_blank)
JOIN assembly_meeting_topic topic ON topic.assembly_meeting_line=assembly.id
JOIN LEFT assembly_meeting_line aml ON aml.topic=topic.id
FROM assembly_meeting assembly
WHERE assembly.state='finished'
GROUP BY assembly.company_id
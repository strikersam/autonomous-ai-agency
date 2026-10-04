```python
def process_reviews():
    agents = [
        {"Agent": "hunter-python", "Attempts": 0, "Reviews": 0, "Submitted": 0, "Merged": 0, "Paid": 0, "Revenue": 0.00, "Cost": 0.00, "Net": 0.00, "Status": "probation", "Slots": 1},
        {"Agent": "hunter-systems", "Attempts": 0, "Reviews": 0, "Submitted": 0, "Merged": 0, "Paid": 0, "Revenue": 0.00, "Cost": 0.00, "Net": 0.00, "Status": "probation", "Slots": 0},
        {"Agent": "hunter-web", "Attempts": 0, "Reviews": 0, "Submitted": 0, "Merged": 0, "Paid": 0, "Revenue": 0.00, "Cost": 0.00, "Net": 0.00, "Status": "probation", "Slots": 1}
    ]
    
    for agent in agents:
        if agent["Reviews"] < 3:
            agent["Reviews"] += 1
            agent["Revenue"] = agent["Reviews"] * 0.05
            agent["Cost"] = agent["Reviews"] * 0.10
            agent["Net"] = agent["Revenue"] - agent["Cost"]
            if agent["Net"] > 0:
                agent["Status"] = "active"
            elif agent["Net"] == 0:
                agent["Status"] = "probation"
            else:
                agent["Status"] = "retired"
    
    agency_total = {
        "Revenue": sum(agent["Revenue"] for agent in agents),
        "Cost": sum(agent["Cost"] for agent in agents),
        "Net": sum(agent["Net"] for agent in agents)
    }
    
    print("\nAgency total: revenue ${:.2f}, cost ${:.2f}, net ${:.2f}".format(
        agency_total["Revenue"], agency_total["Cost"], agency_total["Net"]
    ))
    
    for agent in agents:
        print("\n|", end="")
        print("{:11}|".format(agent["Agent"]), end="")
        print("{:7}|".format(str(agent["Attempts"])), end="")
        print("{:7}|".format(str(agent["Reviews"])), end="")
        print("{:8}|".format(str(agent["Submitted"])), end="")
        print("{:8}|".format(str(agent["Merged"])), end="")
        print("{:8}|".format(str(agent["Paid"])), end="")
        print("${:.2f}|".format(agent["Revenue"]), end="")
        print("${:.2f}|".format(agent["Cost"]), end="")
        print("\n")
```
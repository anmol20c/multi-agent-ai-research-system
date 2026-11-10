from agents import build_reader_agent, build_search_agent,writer_chain,critic_chain
import time
def run_research_pipeline(topic:str) -> dict:
    state ={}

    time.sleep(1.5)

    #search agent working
    print("\n"+" ="*50)
    print("step 1 - search agent is working...")
    print("="*50)

    search_agent = build_search_agent()
    search_result = search_agent.invoke({
        "messages" : [("user" , f"Find recent, reliable and detailed information about: {topic}")]
    })
    state["search_results"] = search_result['messages'][-1].content
    print("\n search result", state['search_results'])

    time.sleep(1.5)
    
    #step 2 - reader agent
    print("\n"+" ="*50)
    print("step 1 - reader agent is scraping top resources...")
    print("="*50)

    reader_agent = build_reader_agent()
    print("Reader Agent started...")
    reader_result = reader_agent.invoke({
        "messages": [("user",
            f"Based on the following search results about '{topic}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}"
        )]
    })
    print("Reader Agent completed!")
    state['scraped_content'] = reader_result['messages'][-1].content
    print("\nscraped content: \n", state['scraped_content'])

    time.sleep(1.5)

    #step 3 - writer chain
    print("\n"+" ="*50)
    print("step 3 - writer is  drafting the report...")
    print("="*50)
    research_combined = (
        f"SEARCH RESULTS :\n {state['search_results']}\n\n"
        f"DETAILED SCCRAPED CONTENT : \n {state['scraped_content']}"
    )
    state["report"] = writer_chain.invoke({
        "topic" : topic , 
        "research" : research_combined
    })

    print("\n Final Report\n", state['report'])

    time.sleep(1.5)

    #critic report
    print("\n"+" ="*50)
    print("step 4 - critic is  reviewing the report...")
    print("="*50)

    state["feedback"] = critic_chain.invoke({
        "report" : state['report']
    })
    print("\n critic report \n", state['feedback'])

    return state
if __name__ == "__main__":
    topic = input("\n Enter a research topic: ")
    run_research_pipeline(topic)
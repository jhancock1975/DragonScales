# Security first. 
* on merge of a feature branch to main do a...
    * check for un-secure coding practices
    * static security scan
    * dynamic security scan
     
# Do not let file sizes get too large, you will get into problems due to exceeding your context window size and output length constraints.

# break up large read/writes into manageable chunks

# at milestones
* After major milestones, ask if we should commit and push
* clean up dead, duplicated code, 
* simplify logic where possible
* ensure documentationis up-to-date

# TDD
* Use test driven-development
* write tests for new code as we go so we do not get stuck with tons of code that is not covered and we have to go back and write tests
* put end-to-end tests in a separate folder
* a test should not take longer than a second to run
* produce html reports of test results
* we require 95% code coverage
* ensure log output is captured in reports. ensure all tests provide output that shows up in the html reports. the test that is running and its location should always be reported, as well as the length of time to execute the test.

# use automation
* for type safety
* linting
* fixing code smells

# branching and commits
* work in a branch and merge to main at milestones
* use feature branches
* make pull requests to merge to main at milestones
* do not commit IDE project configuration files


# containerization
* the application should be containerized
* run the application from docker

# package maagement
* use uv
* use virtual environment
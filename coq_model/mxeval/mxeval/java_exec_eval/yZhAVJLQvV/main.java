import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class Solution{
  public List<Integer> parseNestedParens(String paren_string){
    String[] groups = paren_string.split(" ");
    List<Integer> result = new ArrayList<>(List.of());
    for (String group : groups){
      if (group.length() > 0){
        int depth = 0;
        int max_depth = 0;
        for (char c : group.toCharArray()){
          if (c == '('){
            depth = depth + 1;
            max_depth = Math.max(depth, max_depth);
          } else {
            depth = depth - 1;
          }
        }
        result.add(max_depth);
      }
    }
    return result;
  }
}class Main {
    public static void main(String[] args) {
        Solution s = new Solution();
        List<Boolean> correct = Arrays.asList(
                s.parseNestedParens("(()()) ((())) () ((())()())").equals(Arrays.asList(2, 3, 1, 3)),
                s.parseNestedParens("() (()) ((())) (((())))").equals(Arrays.asList(1, 2, 3, 4)),
                s.parseNestedParens("(()(())((())))").equals(Arrays.asList(4))
        );
        if (correct.contains(false)) {
            throw new AssertionError();
        }
    }
}
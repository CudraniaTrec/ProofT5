import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FindSubstring{
  public static Boolean findSubstring(List<String> str1, String subStr){
    for (int i = 0; i < str1.size(); i++){
      if (str1.get(i).equals(subStr)){
        return true;
      }
      if (str1.get(i).contains(subStr)){
        return true;
      }
    }
    return false;
  }
}

class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        List<String> arg00 = Arrays.asList("red", "black", "white", "green", "orange");
        String arg01 = "ack";
        Boolean x0 = FindSubstring.findSubstring(Arrays.asList("red", "black", "white", "green", "orange"), "ack");
        Boolean v0 = true;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<String> arg10 = Arrays.asList("red", "black", "white", "green", "orange");
        String arg11 = "abc";
        Boolean x1 = FindSubstring.findSubstring(Arrays.asList("red", "black", "white", "green", "orange"), "abc");
        Boolean v1 = false;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<String> arg20 = Arrays.asList("red", "black", "white", "green", "orange");
        String arg21 = "ange";
        Boolean x2 = FindSubstring.findSubstring(Arrays.asList("red", "black", "white", "green", "orange"), "ange");
        Boolean v2 = true;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
